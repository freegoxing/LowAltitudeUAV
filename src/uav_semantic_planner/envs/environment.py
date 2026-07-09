"""
UAV 强化学习环境模块

实现基于 UAV 语义通信网络图谱的强化学习环境 (UAVRLEnvironment)，
专注于通过 SNR 状态进行通信链路路由规划。
"""

from collections import defaultdict

import numpy as np
import torch
from torch_geometric.data import Data

NodeMap = dict[int, str]
RelationMap = dict[str, int]


class UAVEpisodeState:
    """封装单个 episode 的动态状态，聚焦于 SNR 和链路路由"""

    def __init__(self, start_node, target_node, initial_potential=0.0):
        self.current_node = start_node
        self.target_node = target_node
        self.path = [start_node]
        self.visited = {start_node}
        self.step_count = 0
        self.snr_history = []  # 记录每跳链路的 SNR
        self.path_min_snr = float("inf")  # 木桶效应：路径中的瓶颈 SNR
        self.previous_potential = initial_potential
        self.done = False


class UAVRLEnvironment:
    """UAV 通信网络强化学习路由环境 (纯 SNR 驱动)"""

    def __init__(
        self,
        data: Data,
        node_map: NodeMap,
        relation_map: RelationMap,
        node_embeddings: torch.Tensor,
        max_path_length: int,
        pagerank_values: dict[int, float],
        snr_map: dict[tuple[int, int], float],
        weak_link_set: set[tuple[int, int]],
        node_types: torch.Tensor | None = None,
        snr_threshold: float = 3.0,
        reward_weights: list[
            float
        ] = None,  # Agent 2 下发的权重 [w_snr_gain, w_bottleneck, w_stability]
    ):
        # 静态图资源 (不可变)
        self.data = data
        self.node_map = node_map
        self.relation_map = relation_map
        self.id_to_relation_name = {v: k for k, v in relation_map.items()}

        self.node_embeddings = node_embeddings
        self.num_nodes = data.num_nodes
        self.max_path_length = max_path_length
        self.pagerank_values = pagerank_values
        self.node_types = node_types

        # UAV 通信特有属性
        self.snr_map = snr_map
        self.weak_link_set = weak_link_set
        self.snr_threshold = snr_threshold

        # 奖励参数 (默认权重，如果 Agent 2 没有下发的话)
        self.reward_weights = (
            reward_weights if reward_weights is not None else [1.0, 1.0, 1.0]
        )

        # 构建包含 SNR 信息的邻接表
        self.adjacency_list = self._build_adjacency_list()

        # 当前单例 episode 状态
        self.state: UAVEpisodeState | None = None

    def _build_adjacency_list(self) -> dict[int, list[tuple[int, int, float]]]:
        """构建包含邻居节点、关系ID和SNR的邻接表"""
        adj = defaultdict(list)
        edge_index = self.data.edge_index
        edge_type = self.data.edge_type
        for i in range(edge_index.shape[1]):
            src, tgt = edge_index[0, i].item(), edge_index[1, i].item()
            rel = edge_type[i].item()
            snr = self.snr_map.get((src, tgt), 0.0)
            adj[src].append((tgt, rel, snr))
        return adj

    def _calculate_potential(self, node_id: int, target_node: int) -> float:
        """核心势能算子 (计算节点特征在目标方向上的对齐度)"""
        node_emb = self.node_embeddings[node_id].view(1, -1)
        target_emb = self.node_embeddings[target_node].view(1, -1)
        return torch.cosine_similarity(node_emb, target_emb, eps=1e-8).item()

    def reset(self, start_node: int, target_node: int) -> int:
        """重置单例 episode"""
        p = self._calculate_potential(start_node, target_node)
        self.state = UAVEpisodeState(start_node, target_node, p)
        return start_node

    def reset_batch(
        self, batch_pairs: list[tuple[int, int]], device
    ) -> list[UAVEpisodeState]:
        """批量重置：高效初始化多个 EpisodeState"""
        starts = torch.tensor([s for s, t in batch_pairs], device=device)
        targets = torch.tensor([t for s, t in batch_pairs], device=device)

        # 向量化算势能
        start_embs = self.node_embeddings[starts]
        target_embs = self.node_embeddings[targets]
        pots = torch.cosine_similarity(start_embs, target_embs, eps=1e-8).cpu().numpy()

        return [UAVEpisodeState(s, t, float(p)) for (s, t), p in zip(batch_pairs, pots)]

    def get_valid_actions(self, state: UAVEpisodeState | None = None) -> list[int]:
        """动作空间约束：仅允许通过合规的通信链路（非断连预警链路）"""
        curr_state = state if state is not None else self.state
        if curr_state is None:
            return []

        neighbors_with_info = self.adjacency_list.get(curr_state.current_node, [])
        valid_actions = []

        for n, rel_id, snr in neighbors_with_info:
            if n in curr_state.visited:
                continue

            # Mask 掉 SNR 极低的不可用链路
            if (
                snr >= self.snr_threshold
                and (curr_state.current_node, n) not in self.weak_link_set
            ):
                valid_actions.append(n)

        return valid_actions

    def _compute_reward_internal(
        self,
        state: UAVEpisodeState,
        action: int,
        current_potential: float,
        link_snr: float,
    ) -> tuple[float, bool, dict]:
        """
        核心奖励函数：基于 SNR 态势感知的资源路由评估
        """
        state.step_count += 1

        # 提取动态奖励权重 W (来自 LLM Agent 2)
        w_snr_gain, w_bottleneck, w_stability = self.reward_weights

        # 1. 计算 SNR 奖励特征
        # 记录路径新 SNR 并更新木桶短板 (bottleneck)
        state.snr_history.append(link_snr)
        new_min_snr = min(state.path_min_snr, link_snr)
        snr_drop = (
            state.path_min_snr - new_min_snr
            if state.path_min_snr != float("inf")
            else 0.0
        )
        state.path_min_snr = new_min_snr

        # R_snr_gain: 当前链路的绝对信噪比带来的正向激励 (归一化到约 0~2 的范围)
        r_snr_gain = link_snr / 10.0

        # R_bottleneck: 惩罚使得整个路径短板下降的跳数
        r_bottleneck = -snr_drop

        # R_stability: 惩罚 SNR 序列的剧烈波动 (方差)
        r_stability = 0.0
        if len(state.snr_history) > 1:
            r_stability = -np.var(state.snr_history) / 10.0

        # 2. 计算拓扑势能变化 (逼近目标节点)
        delta_sim = current_potential - state.previous_potential
        r_potential = (delta_sim * 100.0) if delta_sim > 0 else (delta_sim * 20.0)
        state.previous_potential = current_potential

        # 3. 总步进奖励融合
        reward = (
            w_snr_gain * r_snr_gain
            + w_bottleneck * r_bottleneck
            + w_stability * r_stability
            + r_potential
            - 0.5  # -0.5 是基础跳数惩罚
        )

        # 4. 状态转移
        state.current_node = action
        state.path.append(action)
        state.visited.add(action)

        # 5. 终止逻辑
        done = False
        info = {
            "link_snr": link_snr,
            "path_min_snr": state.path_min_snr,
            "snr_variance": np.var(state.snr_history)
            if len(state.snr_history) > 1
            else 0.0,
        }

        if state.current_node == state.target_node:
            # 成功抵达目标节点，结算最终奖励
            # 基础成功奖励
            base_success_reward = 1000.0

            # 木桶效应加成：如果整个端到端路由的最低 SNR 依然很高，给予极大奖励
            bottleneck_bonus = base_success_reward * (
                max(0, state.path_min_snr - self.snr_threshold) / 10.0
            )

            # 效率加成：跳数越少越好
            efficiency_bonus = base_success_reward * (
                (self.max_path_length - state.step_count) / self.max_path_length
            )

            reward += base_success_reward + bottleneck_bonus + efficiency_bonus
            done = True
            info["status"] = "success"

        elif state.step_count >= self.max_path_length:
            reward -= 50.0  # 超时重罚
            done = True
            info["status"] = "timeout"

        state.done = done
        return reward, done, info

    def step(self, action: int) -> tuple[int, float, bool, dict]:
        """单实例步进"""
        valid_actions = self.get_valid_actions(self.state)
        if action not in valid_actions:
            self.state.done = True
            return (
                self.state.current_node,
                -50.0,
                True,
                {"status": "invalid_action", "link_snr": 0.0},
            )

        # 获取目标节点链路 SNR
        neighbors = self.adjacency_list.get(self.state.current_node, [])
        link_snr = 0.0
        for n, rel_id, snr in neighbors:
            if n == action:
                link_snr = snr
                break

        p = self._calculate_potential(action, self.state.target_node)
        reward, done, info = self._compute_reward_internal(
            self.state, action, p, link_snr
        )
        return self.state.current_node, reward, done, info

    def step_batch(
        self,
        batch_states: list[UAVEpisodeState],
        actions: list[int | None],
        potentials: np.ndarray,
    ) -> list[tuple[float, bool, dict]]:
        """批量步进"""
        results = []
        for i, state in enumerate(batch_states):
            action = actions[i]
            if action is None or state.done:
                state.done = True
                results.append((0.0, True, {"status": "already_done"}))
                continue

            valid_actions = self.get_valid_actions(state)
            if action not in valid_actions:
                state.done = True
                results.append(
                    (-50.0, True, {"status": "invalid_action", "link_snr": 0.0})
                )
                continue

            # 获取通信链路 SNR
            neighbors = self.adjacency_list.get(state.current_node, [])
            link_snr = 0.0
            for n, rel_id, snr in neighbors:
                if n == action:
                    link_snr = snr
                    break

            res = self._compute_reward_internal(
                state, action, float(potentials[i]), link_snr
            )
            results.append(res)
        return results
