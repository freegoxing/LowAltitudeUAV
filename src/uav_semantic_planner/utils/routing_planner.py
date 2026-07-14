"""
UAV 语义通信网络资源路由规划器

封装了基于强化学习 (RL) 策略在通信网络拓扑中进行寻路和推演的核心逻辑，
并补充任务通信规范（MCS）与任务通信子图规划能力。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import numpy as np
import torch
from torch_geometric.data import Data

from uav_semantic_planner.envs.environment import UAVRLEnvironment
from uav_semantic_planner.models.models import RLPolicyNet, UAVHGTEncoder


@dataclass(slots=True)
class MissionFlowSpec:
    """Agent 2 输出的单条任务通信流。"""

    flow_id: str
    source: str
    receivers: list[str]
    purpose: str
    priority: int
    bandwidth_req: str | float
    latency_req: str | float
    reliability_req: float
    delivery_mode: str = "anycast"
    command_sync: str = "summary"
    deadline: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "source": self.source,
            "receivers": list(self.receivers),
            "purpose": self.purpose,
            "priority": self.priority,
            "bandwidth_req": self.bandwidth_req,
            "latency_req": self.latency_req,
            "reliability_req": self.reliability_req,
            "delivery_mode": self.delivery_mode,
            "command_sync": self.command_sync,
            "deadline": self.deadline,
        }


@dataclass(slots=True)
class MissionCommunicationSpecification:
    """Agent 2 输出的任务通信规范（MCS）。"""

    mission_id: str
    mission_type: str
    mission_priority: int
    key_nodes: list[str]
    mission_flows: list[MissionFlowSpec]
    resource_budget: dict[str, Any] = field(default_factory=dict)
    backup_requirement: dict[str, int] = field(default_factory=dict)
    healing_policy: dict[str, Any] = field(default_factory=dict)
    command_receiver: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "mission_type": self.mission_type,
            "mission_priority": self.mission_priority,
            "key_nodes": list(self.key_nodes),
            "mission_flows": [flow.to_dict() for flow in self.mission_flows],
            "resource_budget": dict(self.resource_budget),
            "backup_requirement": dict(self.backup_requirement),
            "healing_policy": dict(self.healing_policy),
            "command_receiver": self.command_receiver,
        }


class UAVRoutingPlanner:
    """UAV 路由路径规划器，用于推理主用和备用通信资源路由。"""

    def __init__(self, model_pt_path: str, graph_pt_path: str, device: str = "cpu"):
        self.device = torch.device(device)
        self.model_pt_path = model_pt_path
        self.graph_pt_path = graph_pt_path

        self.raw_id_map: dict[str, int] = {}
        self.node_map: dict[int, str] = {}
        self.env: UAVRLEnvironment | None = None
        self.policy: RLPolicyNet | None = None
        self.node_embeddings: torch.Tensor | None = None

        self._load_models_and_env()

    def _load_models_and_env(self) -> None:
        """加载图谱数据、特征编码器、环境和 RL 策略模型。"""
        if not os.path.exists(self.graph_pt_path):
            raise FileNotFoundError(f"未找到预处理图数据: {self.graph_pt_path}")

        checkpoint = torch.load(
            self.graph_pt_path, map_location=self.device, weights_only=False
        )
        self.raw_id_map = checkpoint["raw_id_map"]
        self.node_map = checkpoint["node_map"]

        num_nodes_dict = checkpoint["num_nodes_dict"]
        total_nodes = sum(num_nodes_dict.values())

        src_list, dst_list, type_list = [], [], []
        relation_map = checkpoint["relation_map"]
        for (ut, rel_name, vt), e_idx in checkpoint["edge_index_dict"].items():
            global_src = checkpoint["x_dict_ids"][ut][e_idx[0]]
            global_dst = checkpoint["x_dict_ids"][vt][e_idx[1]]

            src_list.append(global_src)
            dst_list.append(global_dst)
            type_list.append(torch.full((e_idx.size(1),), relation_map[rel_name]))

        full_edge_index = torch.stack([torch.cat(src_list), torch.cat(dst_list)], dim=0)
        full_edge_type = torch.cat(type_list)
        data = Data(
            edge_index=full_edge_index, edge_type=full_edge_type, num_nodes=total_nodes
        )

        encoder = UAVHGTEncoder(
            num_nodes_dict=num_nodes_dict,
            embedding_dim=128,
            hidden_channels=128,
            out_channels=128,
            metadata=checkpoint["metadata"],
        ).to(self.device)

        h_dict = encoder(
            checkpoint["x_dict_ids"],
            checkpoint["edge_index_dict"],
            checkpoint.get("weak_link_index"),
        )
        self.node_embeddings = torch.zeros(total_nodes, 128, device=self.device)
        for nt, h_tensor in h_dict.items():
            self.node_embeddings[checkpoint["x_dict_ids"][nt]] = h_tensor

        self.env = UAVRLEnvironment(
            data=data,
            node_map=self.node_map,
            relation_map=relation_map,
            node_embeddings=self.node_embeddings,
            max_path_length=10,
            pagerank_values=checkpoint["pagerank_values"],
            snr_map=checkpoint["snr_map"],
            weak_link_set=checkpoint["weak_link_set"],
            node_types=checkpoint["node_types"],
        )

        self.policy = RLPolicyNet(embedding_dim=128, gru_hidden_dim=64).to(self.device)
        if os.path.exists(self.model_pt_path):
            self.policy.load_state_dict(
                torch.load(self.model_pt_path, map_location=self.device, weights_only=True)
            )
        self.policy.eval()

    def _build_masked_edges(self, blocked_nodes: set[int]) -> set[tuple[int, int]]:
        """屏蔽所有经过被占用节点的有向边。"""
        if self.env is None:
            return set()

        masked_edges: set[tuple[int, int]] = set()
        for src, neighbors in self.env.adjacency_list.items():
            for tgt, _, _ in neighbors:
                if src in blocked_nodes or tgt in blocked_nodes:
                    masked_edges.add((src, tgt))
        return masked_edges

    @staticmethod
    def _internal_nodes(path: list[int]) -> set[int]:
        if len(path) <= 2:
            return set()
        return set(path[1:-1])

    def _backup_count_for_flow(
        self, flow: MissionFlowSpec, mission: MissionCommunicationSpecification
    ) -> int:
        """根据任务优先级与显式备份要求推断需要的备份路数。"""
        explicit_key = f"priority_{flow.priority}"
        if explicit_key in mission.backup_requirement:
            return int(mission.backup_requirement[explicit_key])
        if flow.priority >= 5:
            return 2
        if flow.priority >= 4:
            return 1
        return 0

    def _select_flow_receiver(
        self,
        nx_graph: nx.Graph,
        source_name: str,
        candidates: list[str],
        command_receiver: str | None,
        command_sync: str,
    ) -> str:
        """按 Agent 2 给定的 receiver 顺序选择可达终点。"""
        for receiver in candidates:
            if not nx_graph.has_node(receiver):
                continue
            if nx.has_path(nx_graph, source_name, receiver):
                return receiver

        # 指挥车不是默认汇点。仅在 MCS 明确要求立即同步或升级时，
        # 才允许它作为没有可达行动接收者时的兜底终点。
        if (
            command_sync in {"immediate", "on_escalation"}
            and command_receiver
            and nx_graph.has_node(command_receiver)
            and nx.has_path(nx_graph, source_name, command_receiver)
        ):
            return command_receiver

        raise ValueError(f"源节点 '{source_name}' 无法连通到任何合格接收者。")

    def run_inference(
        self, start_int: int, target_int: int, masked_edges: set | None = None
    ) -> tuple[list[int], float]:
        """基于策略进行单次寻路推理，带回溯（Backtracking）逻辑。"""
        if self.env is None or self.policy is None or self.node_embeddings is None:
            raise RuntimeError("路由规划器尚未完成初始化。")

        if masked_edges is None:
            masked_edges = set()

        self.env.reset(start_int, target_int)
        path_memory = torch.zeros(1, 64, device=self.device)
        stack = []
        tried_actions: dict[int, set[int]] = {start_int: set()}
        target_emb = self.node_embeddings[target_int].unsqueeze(0)

        while not self.env.state.done:
            curr_node = self.env.state.current_node
            curr_emb = self.node_embeddings[curr_node].unsqueeze(0)

            valid_actions = self.env.get_valid_actions()
            valid_actions = [
                action for action in valid_actions if (curr_node, action) not in masked_edges
            ]
            if curr_node not in tried_actions:
                tried_actions[curr_node] = set()
            valid_actions = [
                action for action in valid_actions if action not in tried_actions[curr_node]
            ]

            if not valid_actions:
                if stack:
                    print(f"  [预警] {self.node_map[curr_node]} 遭遇死胡同，执行战术回溯...")
                    prev_memory, prev_node, prev_visited = stack.pop()
                    self.env.state.current_node = prev_node
                    self.env.state.visited = prev_visited.copy()
                    self.env.state.path.pop()
                    self.env.state.snr_history.pop()
                    self.env.state.path_min_snr = (
                        min(self.env.state.snr_history)
                        if self.env.state.snr_history
                        else float("inf")
                    )
                    path_memory = prev_memory
                    continue

                print("  [状态] 彻底遭遇网络死胡同 (无符合 SNR 阈值的下一跳)")
                break

            neighbor_embs = self.node_embeddings[valid_actions].unsqueeze(0)
            neighbor_mask = torch.ones(1, len(valid_actions), dtype=torch.float32)

            with torch.no_grad():
                action_dist, _, next_memory = self.policy(
                    curr_emb, target_emb, neighbor_embs, path_memory, neighbor_mask
                )

            if action_dist is None:
                break

            best_action_idx = action_dist.logits.argmax(dim=-1).item()
            chosen_action = valid_actions[best_action_idx]
            tried_actions[curr_node].add(chosen_action)
            stack.append((path_memory.clone(), curr_node, self.env.state.visited.copy()))
            self.env.step(chosen_action)
            path_memory = next_memory
            print(
                f"  -> 路由跳跃至: {self.node_map[chosen_action]} "
                f"(瓶颈 SNR: {self.env.state.path_min_snr}dB)"
            )

        return self.env.state.path, self.env.state.path_min_snr

    def plan_routing(
        self,
        start_node_name: str,
        target_node_name: str,
        backup_count: int = 1,
    ) -> dict[str, Any]:
        """根据起点和终点名称，规划主用和备用路由。"""
        if start_node_name not in self.raw_id_map:
            raise ValueError(f"起点 '{start_node_name}' 不在图谱中。")
        if target_node_name not in self.raw_id_map:
            raise ValueError(f"目标终点 '{target_node_name}' 不在图谱中。")

        start_int = self.raw_id_map[start_node_name]
        target_int = self.raw_id_map[target_node_name]

        print(f"\n[计算主用路径...] ({start_node_name} -> {target_node_name})")
        primary_path, primary_min_snr = self.run_inference(start_int, target_int)
        if not primary_path or primary_path[-1] != target_int:
            print("  [状态] 未能抵达目标节点，不将半路径作为有效主路径。")
            return {
                "status": "unreachable",
                "primary_path": [],
                "primary_min_snr": 0.0,
                "backup_path": [],
                "backup_min_snr": 0.0,
                "backup_paths": [],
                "backup_min_snrs": [],
            }

        backup_paths: list[list[int]] = []
        backup_min_snrs: list[float] = []
        blocked_nodes = self._internal_nodes(primary_path)
        masked_edges = set(zip(primary_path[:-1], primary_path[1:]))

        for _ in range(max(0, backup_count)):
            if self.env is None:
                break

            masked_edges |= self._build_masked_edges(blocked_nodes)
            backup_path, backup_min_snr = self.run_inference(
                start_int, target_int, masked_edges
            )

            if (
                len(backup_path) <= 1
                or backup_path[-1] != target_int
                or backup_path == primary_path
            ):
                break

            backup_paths.append(backup_path)
            backup_min_snrs.append(backup_min_snr)
            blocked_nodes |= self._internal_nodes(backup_path)
            masked_edges |= set(zip(backup_path[:-1], backup_path[1:]))

        if backup_paths:
            primary_score = primary_min_snr * 10 - len(primary_path)
            backup_score = backup_min_snrs[0] * 10 - len(backup_paths[0])
            if backup_score > primary_score:
                print(
                    "\n[智能调整] 发现备用路径质量优于原规划主路径，自动进行主备路由翻转换路！"
                )
                primary_path, backup_paths[0] = backup_paths[0], primary_path
                primary_min_snr, backup_min_snrs[0] = backup_min_snrs[0], primary_min_snr

        primary_path_names = [self.node_map[n] for n in primary_path]
        backup_path_names = [
            [self.node_map[n] for n in path] for path in backup_paths
        ]

        return {
            "status": "planned",
            "primary_path": primary_path_names,
            "primary_min_snr": primary_min_snr,
            "backup_path": backup_path_names[0] if backup_path_names else [],
            "backup_min_snr": backup_min_snrs[0] if backup_min_snrs else 0.0,
            "backup_paths": backup_path_names,
            "backup_min_snrs": backup_min_snrs,
        }

    def plan_mission_communication(
        self,
        mission: MissionCommunicationSpecification,
        nx_graph: nx.Graph,
    ) -> dict[str, Any]:
        """根据任务通信规范规划任务通信子图。"""
        if not mission.mission_flows:
            raise ValueError("mission_flows 不能为空。")

        flow_results: list[dict[str, Any]] = []
        subgraph_edges: set[tuple[str, str]] = set()
        relay_nodes: set[str] = set()

        for flow in mission.mission_flows:
            try:
                selected_receiver = self._select_flow_receiver(
                    nx_graph=nx_graph,
                    source_name=flow.source,
                    candidates=flow.receivers,
                    command_receiver=mission.command_receiver,
                    command_sync=flow.command_sync,
                )
            except ValueError as exc:
                flow_results.append(
                    {
                        "flow": flow.to_dict(),
                        "status": "unreachable",
                        "selected_receiver": "",
                        "primary_path": [],
                        "primary_min_snr": 0.0,
                        "backup_paths": [],
                        "backup_min_snrs": [],
                        "relay_nodes": [],
                        "reserved_resources": {},
                        "reason": str(exc),
                    }
                )
                continue

            backup_count = self._backup_count_for_flow(flow, mission)
            route_result = self.plan_routing(
                flow.source, selected_receiver, backup_count=backup_count
            )

            primary_path = route_result["primary_path"]
            backup_paths = route_result["backup_paths"]
            selected_backup_paths = backup_paths if backup_paths else []

            for path in [primary_path, *selected_backup_paths]:
                subgraph_edges.update(zip(path[:-1], path[1:]))
                relay_nodes.update(node for node in path[1:-1])

            reserved_resources = {
                "bandwidth_budget": mission.resource_budget.get("mission_bandwidth_cap"),
                "relay_count_cap": mission.resource_budget.get("relay_count_cap"),
                "power_ceiling": mission.resource_budget.get("power_ceiling"),
                "path_hops": max(0, len(primary_path) - 1),
                "backup_paths": len(selected_backup_paths),
            }

            flow_results.append(
                {
                    "flow": flow.to_dict(),
                    "status": route_result["status"],
                    "selected_receiver": selected_receiver,
                    "primary_path": primary_path,
                    "primary_min_snr": route_result["primary_min_snr"],
                    "backup_paths": selected_backup_paths,
                    "backup_min_snrs": route_result["backup_min_snrs"],
                    "relay_nodes": list(dict.fromkeys(primary_path[1:-1])),
                    "reserved_resources": reserved_resources,
                }
            )

        return {
            "mission": mission.to_dict(),
            "flow_results": flow_results,
            "task_communication_subgraph": {
                "nodes": sorted(
                    set(mission.key_nodes)
                    | relay_nodes
                    | {item["flow"]["source"] for item in flow_results}
                    | {
                        item["selected_receiver"]
                        for item in flow_results
                        if item["selected_receiver"]
                    }
                ),
                "edges": sorted(subgraph_edges),
            },
            "selected_receivers": {
                item["flow"]["flow_id"]: item["selected_receiver"] for item in flow_results
            },
        }

    def select_routing_endpoints(
        self, nx_graph: nx.Graph, tgt_node: str = "", auto_find: bool = False
    ) -> tuple[str, str]:
        """
        兼容旧原型的端点选择接口。

        新的任务规划流程应优先使用 plan_mission_communication。
        """
        gnd_c_nodes = [k for k, v in self.node_map.items() if "GND-C" in v]
        if not gnd_c_nodes:
            raise ValueError("图谱中没有找到指挥中心 (GND-C) 节点！")

        start_int, target_int = None, None

        if tgt_node:
            if tgt_node not in self.raw_id_map:
                raise ValueError(f"节点 '{tgt_node}' 不在图谱中，请检查名称。")
            start_int = self.raw_id_map[tgt_node]

            for t in gnd_c_nodes:
                if nx.has_path(nx_graph, self.node_map[start_int], self.node_map[t]):
                    target_int = t
                    break

            if target_int is None:
                raise ValueError(f"节点 '{tgt_node}' 无法连通到任何指挥中心 (GND-C)！")

        elif auto_find:
            print("--- 正在自动寻找从侦察节点或救援人员到指挥中心(GND-C)的可达路径 ---")
            source_nodes = [
                k for k, v in self.node_map.items() if "UAV-S" in v or "GND-P" in v
            ]

            import random

            random.shuffle(source_nodes)
            random.shuffle(gnd_c_nodes)

            found = False
            for s in source_nodes:
                for t in gnd_c_nodes:
                    if nx.has_path(nx_graph, self.node_map[s], self.node_map[t]):
                        start_int, target_int = s, t
                        found = True
                        break
                if found:
                    break

        if start_int is None or target_int is None:
            start_int = self.raw_id_map.get("UAV-S-1", 0)
            target_int = self.raw_id_map.get("GND-C-1", 1)

        return self.node_map[start_int], self.node_map[target_int]
