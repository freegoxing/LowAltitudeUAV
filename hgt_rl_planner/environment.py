"""
强化学习环境模块

实现基于知识图谱的强化学习环境 (RLEnvironment)，专门适配大规模异构教育图谱。
"""

from collections import defaultdict

import numpy as np
import torch
from torch_geometric.data import Data

NodeMap = dict[int, str]
RelationMap = dict[str, int]


class EpisodeState:
    """封装单个 episode 的动态状态，与静态图解耦"""

    def __init__(self, start_node, target_node, initial_potential):
        self.current_node = start_node
        self.target_node = target_node
        self.path = [start_node]
        self.visited = {start_node}
        self.step_count = 0
        self.previous_potential = initial_potential
        self.done = False


class RLEnvironment:
    """强化学习环境 (适配 MOOCCubex 异构版)"""

    def __init__(
        self,
        data: Data,
        node_map: NodeMap,
        relation_map: RelationMap,
        node_embeddings: torch.Tensor,
        max_path_length: int,
        pagerank_values: dict[int, float],
        prerequisite_map: dict[int, set[int]],
        node_types: torch.Tensor | None = None,
        reward_alpha: float = 0.1,
        reward_eta: float = 1.0,
        reward_lambda: float = 5.0,
        reward_clipping_value: float | None = 0.3,
        reward_ema_alpha: float = 0.1,
        pagerank_exploration_steps: int = 3,
        max_prereq_penalty_count: int = 3,
        soft_skip_penalty_scale: float = 0.15,
        other_skip_penalty_scale: float = 0.30,
        constraint_mode: str = "hybrid",  # ['strict', 'hybrid', 'soft']
        ablate_soft_relations: bool = False,  # [新增] 消融血肉：仅保留先修骨架边
    ):
        # 静态图资源 (不可变)
        self.data = data
        self.node_map = node_map
        self.relation_map = relation_map
        self.id_to_relation_name = {v: k for k, v in relation_map.items()}
        self.prereq_relation_id = relation_map.get("prerequisite", -1)
        self.ablate_soft_relations = ablate_soft_relations

        self.node_embeddings = node_embeddings
        self.num_nodes = data.num_nodes
        self.max_path_length = max_path_length
        self.pagerank_values = pagerank_values
        self.prerequisite_map = prerequisite_map
        self.node_types = node_types
        self.constraint_mode = constraint_mode
        self.adjacency_list = self._build_adjacency_list()

        # 奖励参数
        self.REWARD_ALPHA = reward_alpha
        self.REWARD_ETA = reward_eta
        self.REWARD_LAMBDA = reward_lambda
        self.reward_clipping_value = reward_clipping_value
        self.reward_ema_alpha = reward_ema_alpha
        self.pagerank_exploration_steps = pagerank_exploration_steps
        # 先修惩罚参数：限制单步惩罚上限，避免训练前期被大额负回报淹没
        self.max_prereq_penalty_count = max(1, int(max_prereq_penalty_count))
        self.soft_skip_penalty_scale = float(soft_skip_penalty_scale)
        self.other_skip_penalty_scale = float(other_skip_penalty_scale)

        # 当前单例 episode 状态 (仅为了兼容旧接口)
        self.state: EpisodeState | None = None

    def _build_adjacency_list(self) -> dict[int, list[tuple[int, int]]]:
        adj = defaultdict(list)
        edge_index = self.data.edge_index
        edge_type = self.data.edge_type
        for i in range(edge_index.shape[1]):
            src, tgt = edge_index[0, i].item(), edge_index[1, i].item()
            rel = edge_type[i].item()
            # 如果开启了血肉消融，则过滤掉所有非先修边
            if self.ablate_soft_relations and rel != self.prereq_relation_id:
                continue
            adj[src].append((tgt, rel))
        return adj

    def _calculate_potential(self, node_id: int, target_node: int) -> float:
        """核心势能算子 (无副作用)"""
        node_emb = self.node_embeddings[node_id].view(1, -1)
        target_emb = self.node_embeddings[target_node].view(1, -1)
        return torch.cosine_similarity(node_emb, target_emb, eps=1e-8).item()

    def reset(self, start_node: int, target_node: int) -> int:
        """重置单例 episode (兼容旧逻辑)"""
        p = self._calculate_potential(start_node, target_node)
        self.state = EpisodeState(start_node, target_node, p)
        return start_node

    def reset_batch(
        self, batch_pairs: list[tuple[int, int]], device
    ) -> list[EpisodeState]:
        """批量重置：高效初始化多个 EpisodeState"""
        starts = torch.tensor([s for s, t in batch_pairs], device=device)
        targets = torch.tensor([t for s, t in batch_pairs], device=device)

        # 向量化算势能
        start_embs = self.node_embeddings[starts]
        target_embs = self.node_embeddings[targets]
        pots = torch.cosine_similarity(start_embs, target_embs, eps=1e-8).cpu().numpy()

        return [EpisodeState(s, t, float(p)) for (s, t), p in zip(batch_pairs, pots)]

    def get_valid_actions(self, state: EpisodeState | None = None) -> list[int]:
        """核心动作空间探测逻辑：支持关系感知约束"""
        curr_state = state if state is not None else self.state
        if curr_state is None:
            return []

        neighbors_with_rels = self.adjacency_list.get(curr_state.current_node, [])
        valid_actions = []

        for n, rel_id in neighbors_with_rels:
            if n in curr_state.visited:
                continue

            # 模式识别
            is_prereq_edge = rel_id == self.prereq_relation_id
            prereqs_of_target = self.prerequisite_map.get(n, set())
            all_prereqs_met = all(p in curr_state.visited for p in prereqs_of_target)

            if self.constraint_mode == "strict":
                # 严格模式：任何边都必须满足目标节点的所有先修
                if all_prereqs_met:
                    valid_actions.append(n)
            elif self.constraint_mode == "hybrid":
                # 混合模式：先修边必须合规，软边（video/test等）允许在先修未完全满足时探索
                if is_prereq_edge:
                    if all_prereqs_met:
                        valid_actions.append(n)
                else:
                    # 软边允许探索
                    valid_actions.append(n)
            elif self.constraint_mode == "soft":
                # 全放开模式
                valid_actions.append(n)

        return valid_actions

    def _compute_reward_internal(
        self,
        state: EpisodeState,
        action: int,
        current_potential: float,
        is_prereq_edge: bool = False,
        is_soft_edge: bool = False,
    ) -> tuple[float, bool, dict]:
        """
        核心奖励函数：区分软边路径与先修合规性，提供精准反馈。
        """
        state.step_count += 1

        # 1. 检查目标节点的先修缺失情况 (诊断指标：Neuro-Symbolic 逻辑)
        prereqs_of_target = self.prerequisite_map.get(action, set())
        missing_prereqs = [p for p in prereqs_of_target if p not in state.visited]
        p_skip_count = len(missing_prereqs)

        # 2. 势能变化奖励
        delta_sim = current_potential - state.previous_potential
        reward = (delta_sim * 400.0) if delta_sim > 0 else (delta_sim * 40.0)

        # 更新状态势能
        state.previous_potential = current_potential

        # 3. 约束惩罚 (精细化反馈)
        if p_skip_count > 0:
            # 限制单步违例数量的惩罚上限，提升前期探索稳定性
            capped_skip = min(p_skip_count, self.max_prereq_penalty_count)
            if is_prereq_edge:
                # 极其严重：明知有先修依赖，却依然逆向/跳跃走先修边 (Logic Violation)
                reward -= self.REWARD_LAMBDA * 1.0 * capped_skip
            elif is_soft_edge:
                # 中度代价：走软边尝试跳级学习 (Exploration Cost)
                reward -= (
                    self.REWARD_LAMBDA * self.soft_skip_penalty_scale * capped_skip
                )
            else:
                # 其他边跨级
                reward -= (
                    self.REWARD_LAMBDA * self.other_skip_penalty_scale * capped_skip
                )

        # 软边探索的基础成本 (鼓励优先走满足先修的主干)
        if is_soft_edge:
            reward -= 0.2

        # 基础步数惩罚
        reward -= 0.1

        # 4. 状态转移
        state.current_node = action
        state.path.append(action)
        state.visited.add(action)

        # 5. 终止逻辑
        done = False
        info = {
            "p_skip": p_skip_count,
            "mode": self.constraint_mode,
            "is_soft_edge": is_soft_edge,
            "is_prereq_edge": is_prereq_edge,
        }

        if state.current_node == state.target_node:
            # 到达终点：检查路径完整性（是否满足了目标的所有先修）
            target_prereqs = self.prerequisite_map.get(state.target_node, set())
            all_target_prereqs_met = all(p in state.visited for p in target_prereqs)

            base_success_reward = 2000.0
            if not all_target_prereqs_met:
                # 成功但“跳读”，奖励折损
                base_success_reward *= 0.5
                info["prereq_satisfied"] = False
            else:
                info["prereq_satisfied"] = True

            path_efficiency = (
                self.max_path_length - state.step_count
            ) / self.max_path_length
            efficiency_bonus = base_success_reward * (path_efficiency**2) * 2.0
            reward += base_success_reward + efficiency_bonus
            done = True
            info["status"] = "success"

        elif state.step_count >= self.max_path_length:
            reward -= 10.0
            done = True
            info["status"] = "timeout"

        state.done = done
        return reward, done, info

    def step(self, action: int) -> tuple[int, float, bool, dict]:
        """单实例步进 (带边类型识别)"""
        valid_actions = self.get_valid_actions(self.state)
        if action not in valid_actions:
            self.state.done = True
            return (
                self.state.current_node,
                -10.0,
                True,
                {
                    "status": "invalid_action",
                    "mode": self.constraint_mode,
                    "is_soft_edge": False,
                    "is_prereq_edge": False,
                    "p_skip": 0,
                },
            )

        # 识别当前动作对应的边类型
        neighbors = self.adjacency_list.get(self.state.current_node, [])
        is_prereq = False
        is_soft = False
        for n, rel_id in neighbors:
            if n == action:
                is_prereq = rel_id == self.prereq_relation_id
                is_soft = not is_prereq
                break

        p = self._calculate_potential(action, self.state.target_node)
        reward, done, info = self._compute_reward_internal(
            self.state, action, p, is_prereq_edge=is_prereq, is_soft_edge=is_soft
        )
        return self.state.current_node, reward, done, info

    def step_batch(
        self,
        batch_states: list[EpisodeState],
        actions: list[int | None],
        potentials: np.ndarray,
    ) -> list[tuple[float, bool, dict]]:
        """批量步进 (带边类型识别)"""
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
                    (
                        -10.0,
                        True,
                        {
                            "status": "invalid_action",
                            "mode": self.constraint_mode,
                            "is_soft_edge": False,
                            "is_prereq_edge": False,
                            "p_skip": 0,
                        },
                    )
                )
                continue

            # 识别边类型
            neighbors = self.adjacency_list.get(state.current_node, [])
            is_prereq = False
            is_soft = False
            for n, rel_id in neighbors:
                if n == action:
                    is_prereq = rel_id == self.prereq_relation_id
                    is_soft = not is_prereq
                    break

            res = self._compute_reward_internal(
                state,
                action,
                float(potentials[i]),
                is_prereq_edge=is_prereq,
                is_soft_edge=is_soft,
            )
            results.append(res)
        return results
