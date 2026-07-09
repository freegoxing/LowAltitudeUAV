"""
UAV 语义通信网络资源路由规划器

封装了基于强化学习 (RL) 策略在通信网络拓扑中进行寻路和推演的核心逻辑，
支持主用路由、备用路由的规划，以及战术回溯 (Backtracking) 算法和智能路由翻转换路评估。
"""

import os
import json
import torch
import numpy as np
import networkx as nx
from torch_geometric.data import Data

from uav_semantic_planner.envs.environment import UAVRLEnvironment
from uav_semantic_planner.models.models import RLPolicyNet, UAVHGTEncoder


class UAVRoutingPlanner:
    """UAV 路由路径规划器，用于推理主用和备用通信资源路由"""

    def __init__(self, model_pt_path: str, graph_pt_path: str, device: str = "cpu"):
        """
        初始化路由规划器。

        Args:
            model_pt_path (str): 策略模型文件路径 (.pt)
            graph_pt_path (str): 图数据及环境元数据路径 (.pt)
            device (str): 运算设备 ('cpu' 或 'cuda')
        """
        self.device = torch.device(device)
        self.model_pt_path = model_pt_path
        self.graph_pt_path = graph_pt_path

        self.raw_id_map = {}
        self.node_map = {}
        self.env = None
        self.policy = None
        self.node_embeddings = None

        self._load_models_and_env()

    def _load_models_and_env(self):
        """加载图谱数据、特征编码器、环境和 RL 策略模型。"""
        if not os.path.exists(self.graph_pt_path):
            raise FileNotFoundError(f"未找到预处理图数据: {self.graph_pt_path}")

        checkpoint = torch.load(self.graph_pt_path, map_location=self.device, weights_only=False)
        self.raw_id_map = checkpoint["raw_id_map"]  # name -> int
        self.node_map = checkpoint["node_map"]      # int -> name

        # 重新提取 embeddings
        num_nodes_dict = checkpoint["num_nodes_dict"]
        total_nodes = sum(num_nodes_dict.values())

        src_list, dst_list, type_list = [], [], []
        relation_map = checkpoint["relation_map"]
        for (ut, rel_name, vt), e_idx in checkpoint["edge_index_dict"].items():
            # e_idx 是局部索引，需要映射回全局索引
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

        # 为了直接展示寻路能力，使用随机初始化的特征通过 HGT 提取
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

    def run_inference(self, start_int: int, target_int: int, masked_edges: set = None) -> tuple[list[int], float]:
        """
        基于策略进行单次寻路推理，带回溯（Backtracking）逻辑。

        Args:
            start_int (int): 起点节点 ID
            target_int (int): 终点节点 ID
            masked_edges (set): 被屏蔽的边集合，格式为 {(src_id, dst_id), ...}

        Returns:
            tuple[list[int], float]: (寻路节点 ID 列表, 路径最小瓶颈 SNR 值)
        """
        if masked_edges is None:
            masked_edges = set()

        self.env.reset(start_int, target_int)

        # 维护一个探索栈，用于死胡同回溯 (Backtracking)
        # stack element: (path_memory, current_node, visited_set)
        path_memory = torch.zeros(1, 64, device=self.device)
        stack = []
        tried_actions = {start_int: set()}

        target_emb = self.node_embeddings[target_int].unsqueeze(0)

        while not self.env.state.done:
            curr_node = self.env.state.current_node
            curr_emb = self.node_embeddings[curr_node].unsqueeze(0)

            valid_actions = self.env.get_valid_actions()
            # 应用边掩码
            valid_actions = [
                a for a in valid_actions if (curr_node, a) not in masked_edges
            ]
            # 应用本地已尝试的动作掩码 (防止死循环)
            if curr_node not in tried_actions:
                tried_actions[curr_node] = set()
            valid_actions = [
                a for a in valid_actions if a not in tried_actions[curr_node]
            ]

            if not valid_actions:
                # 遭遇死胡同，尝试回溯
                if len(stack) > 0:
                    print(f"  [预警] {self.node_map[curr_node]} 遭遇死胡同，执行战术回溯...")
                    prev_memory, prev_node, prev_visited = stack.pop()

                    # 恢复环境状态
                    self.env.state.current_node = prev_node
                    self.env.state.visited = prev_visited.copy()
                    self.env.state.path.pop()
                    self.env.state.snr_history.pop()
                    # 重新计算 min snr
                    self.env.state.path_min_snr = (
                        min(self.env.state.snr_history)
                        if self.env.state.snr_history
                        else float("inf")
                    )

                    path_memory = prev_memory
                    continue
                else:
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

            # 记录这次选择，如果回溯回来就不再选它
            tried_actions[curr_node].add(chosen_action)

            # 保存当前状态到栈，以便需要时回溯
            stack.append((path_memory.clone(), curr_node, self.env.state.visited.copy()))

            self.env.step(chosen_action)
            path_memory = next_memory
            print(
                f"  -> 路由跳跃至: {self.node_map[chosen_action]} (瓶颈 SNR: {self.env.state.path_min_snr}dB)"
            )

        return self.env.state.path, self.env.state.path_min_snr

    def plan_routing(self, start_node_name: str, target_node_name: str) -> dict:
        """
        根据起点和终点名称，规划主用和备用路由。

        Args:
            start_node_name (str): 起点节点名称
            target_node_name (str): 终点节点名称

        Returns:
            dict: 包含主用路由和备用路由信息的字典:
                {
                    "primary_path": list[str],
                    "primary_min_snr": float,
                    "backup_path": list[str],
                    "backup_min_snr": float
                }
        """
        if start_node_name not in self.raw_id_map:
            raise ValueError(f"起点 '{start_node_name}' 不在图谱中。")
        if target_node_name not in self.raw_id_map:
            raise ValueError(f"目标终点 '{target_node_name}' 不在图谱中。")

        start_int = self.raw_id_map[start_node_name]
        target_int = self.raw_id_map[target_node_name]

        print(f"\n[计算主用路径...] ({start_node_name} -> {target_node_name})")
        primary_path, primary_min_snr = self.run_inference(start_int, target_int)

        # 计算备用路由 (屏蔽主路由的第一跳，迫使网络寻找完全不同的出口)
        backup_path = []
        backup_min_snr = 0.0
        if len(primary_path) > 1:
            print("\n[计算备用路径...]")
            masked_edges = {(primary_path[0], primary_path[1])}
            backup_path, backup_min_snr = self.run_inference(start_int, target_int, masked_edges)

        # 智能比对与路由翻转
        if backup_path and len(backup_path) > 0:
            # 评估指标：瓶颈 SNR 优先，跳数次之
            primary_score = primary_min_snr * 10 - len(primary_path)
            backup_score = backup_min_snr * 10 - len(backup_path)

            if backup_score > primary_score:
                print("\n[智能调整] 发现备用路径质量优于原规划主路径，自动进行主备路由翻转换路！")
                primary_path, backup_path = backup_path, primary_path
                primary_min_snr, backup_min_snr = backup_min_snr, primary_min_snr

        # 将节点 ID 映射回名称
        primary_path_names = [self.node_map[n] for n in primary_path]
        backup_path_names = [self.node_map[n] for n in backup_path] if backup_path else []

        return {
            "primary_path": primary_path_names,
            "primary_min_snr": primary_min_snr,
            "backup_path": backup_path_names,
            "backup_min_snr": backup_min_snr
        }

    def select_routing_endpoints(self, nx_graph: nx.Graph, tgt_node: str = "", auto_find: bool = False) -> tuple[str, str]:
        """
        根据指定条件自动选择起点和终点，确保它们在拓扑中是连通的。

        Args:
            nx_graph (nx.Graph): NetworkX 图实例
            tgt_node (str): 指定的起点名称，为空时采用 auto_find 逻辑
            auto_find (bool): 是否在未指定起点时，自动寻找一个能连通到任意 GND-C 的源节点 (UAV-S 或 GND-P)

        Returns:
            tuple[str, str]: (起点节点名称, 终点节点名称)
        """
        # 强制终点类为指挥中心
        gnd_c_nodes = [k for k, v in self.node_map.items() if "GND-C" in v]
        if not gnd_c_nodes:
            raise ValueError("图谱中没有找到指挥中心 (GND-C) 节点！")

        start_int, target_int = None, None

        if tgt_node:
            if tgt_node not in self.raw_id_map:
                raise ValueError(f"节点 '{tgt_node}' 不在图谱中，请检查名称。")
            start_int = self.raw_id_map[tgt_node]

            # 寻找一个可达的 GND-C
            for t in gnd_c_nodes:
                if nx.has_path(nx_graph, self.node_map[start_int], self.node_map[t]):
                    target_int = t
                    break

            if target_int is None:
                raise ValueError(f"节点 '{tgt_node}' 无法连通到任何指挥中心 (GND-C)！")

        elif auto_find:
            print("--- 正在自动寻找从侦察节点或救援人员到指挥中心(GND-C)的可达路径 ---")
            source_nodes = [k for k, v in self.node_map.items() if "UAV-S" in v or "GND-P" in v]

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

        # 兜底逻辑
        if start_int is None or target_int is None:
            start_int = self.raw_id_map.get("UAV-S-1", 0)
            target_int = self.raw_id_map.get("GND-C-1", 1)

        return self.node_map[start_int], self.node_map[target_int]
