"""
UAV RL 训练器模块

负责协调强化学习（Actor-Critic）在 UAV 语义通信网络上的训练。
处理了批处理、梯度计算和损失聚合。
"""

import torch
import torch.nn.functional as F
import torch.optim as optim

from uav_semantic_planner.envs.environment import UAVRLEnvironment
from uav_semantic_planner.models.models import RLPolicyNet


class RLTrainer:
    """强化学习训练器 (批量版本，用于 UAV 通信路由寻路)"""

    def __init__(
        self,
        env: UAVRLEnvironment,
        policy_net: RLPolicyNet,
        node_embeddings: torch.Tensor,
        device: torch.device,
        learning_rate: float = 0.001,
        gamma: float = 0.99,
        entropy_coef: float = 0.01,
    ):
        self.env = env
        self.policy_net = policy_net.to(device)
        self.node_embeddings = node_embeddings.to(device)
        self.device = device
        self.gamma = gamma
        self.entropy_coef = entropy_coef

        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)

    def _prepare_neighbors(self, state, valid_actions):
        """为单实例准备邻居的 Embedding 和 Mask"""
        if not valid_actions:
            return None, None, None

        neighbor_embs = self.node_embeddings[valid_actions]
        neighbor_mask = torch.ones(
            len(valid_actions), dtype=torch.float32, device=self.device
        )
        actions_tensor = torch.tensor(
            valid_actions, dtype=torch.long, device=self.device
        )
        return neighbor_embs, neighbor_mask, actions_tensor

    def train_batch(
        self, batch_pairs: list[tuple[int, int]]
    ) -> tuple[float, float, torch.Tensor | None]:
        """批量训练 Actor-Critic"""
        batch_size = len(batch_pairs)
        if batch_size == 0:
            return 0.0, 0.0, None

        self.policy_net.train()
        batch_states = self.env.reset_batch(batch_pairs, self.device)

        # RNN 初始隐藏状态
        batch_memory = torch.zeros(
            batch_size, self.policy_net.gru_hidden_dim, device=self.device
        )

        log_probs_list = [[] for _ in range(batch_size)]
        values_list = [[] for _ in range(batch_size)]
        rewards_list = [[] for _ in range(batch_size)]
        entropies_list = [[] for _ in range(batch_size)]

        max_steps = self.env.max_path_length
        step_idx = 0
        active_mask = torch.ones(batch_size, dtype=torch.bool, device=self.device)

        while active_mask.any() and step_idx < max_steps:
            active_indices = active_mask.nonzero(as_tuple=True)[0].cpu().numpy()

            # 收集当前步输入
            current_nodes = [batch_states[i].current_node for i in active_indices]
            target_nodes = [batch_states[i].target_node for i in active_indices]

            curr_embs = self.node_embeddings[current_nodes]
            tgt_embs = self.node_embeddings[target_nodes]
            curr_memories = batch_memory[active_indices]

            # 准备各 instance 的邻居
            all_neighbor_embs = []
            all_neighbor_masks = []
            all_action_tensors = []
            max_neighbors = 0

            for idx in active_indices:
                valid_actions = self.env.get_valid_actions(batch_states[idx])
                n_embs, n_mask, a_tensor = self._prepare_neighbors(
                    batch_states[idx], valid_actions
                )
                all_neighbor_embs.append(n_embs)
                all_neighbor_masks.append(n_mask)
                all_action_tensors.append(a_tensor)
                if n_embs is not None:
                    max_neighbors = max(max_neighbors, n_embs.size(0))

            # 组装 batch neighbor tensors (需 padding)
            if max_neighbors > 0:
                padded_embs = torch.zeros(
                    len(active_indices),
                    max_neighbors,
                    self.policy_net.embedding_dim,
                    device=self.device,
                )
                padded_masks = torch.zeros(
                    len(active_indices), max_neighbors, device=self.device
                )

                for k, (n_embs, n_mask) in enumerate(
                    zip(all_neighbor_embs, all_neighbor_masks)
                ):
                    if n_embs is not None:
                        num_n = n_embs.size(0)
                        padded_embs[k, :num_n, :] = n_embs
                        padded_masks[k, :num_n] = n_mask
            else:
                padded_embs = None
                padded_masks = None

            # 神经网络前向推断
            action_dist, state_values, next_memories = self.policy_net(
                curr_embs, tgt_embs, padded_embs, curr_memories, padded_masks
            )

            # 保存新 memory
            batch_memory[active_indices] = next_memories

            # 采样与交互
            actions_to_env = [None] * batch_size
            step_rewards = [0.0] * batch_size
            step_dones = [True] * batch_size

            if action_dist is not None:
                sampled_action_indices = action_dist.sample()
                log_probs = action_dist.log_prob(sampled_action_indices)
                entropies = action_dist.entropy()

                for k, global_idx in enumerate(active_indices):
                    a_tensor = all_action_tensors[k]
                    if a_tensor is not None and len(a_tensor) > 0:
                        chosen_action_idx = sampled_action_indices[k].item()
                        # 越界保护 (mask 机制可能仍采样到 pad 位置的极小概率)
                        if chosen_action_idx >= len(a_tensor):
                            chosen_action_idx = 0

                        real_action = a_tensor[chosen_action_idx].item()
                        actions_to_env[global_idx] = real_action

                        log_probs_list[global_idx].append(log_probs[k])
                        values_list[global_idx].append(state_values[k].squeeze(-1))
                        entropies_list[global_idx].append(entropies[k])
                    else:
                        active_mask[global_idx] = False
            else:
                for k, global_idx in enumerate(active_indices):
                    active_mask[global_idx] = False

            # Env Batch Step
            # 重新计算一次势能（向量化）以备环境需要，必须是对整个 batch 计算
            all_curr_nodes = [s.current_node for s in batch_states]
            all_tgt_nodes = [s.target_node for s in batch_states]
            all_curr_embs = self.node_embeddings[all_curr_nodes]
            all_tgt_embs = self.node_embeddings[all_tgt_nodes]
            all_pots = (
                torch.cosine_similarity(all_curr_embs, all_tgt_embs, eps=1e-8)
                .cpu()
                .numpy()
            )
            step_results = self.env.step_batch(batch_states, actions_to_env, all_pots)

            for i, (rew, done, info) in enumerate(step_results):
                if active_mask[i]:
                    rewards_list[i].append(rew)
                    if done:
                        active_mask[i] = False

            step_idx += 1

        # 计算总损失
        total_loss = torch.tensor(0.0, device=self.device)
        total_reward = 0.0
        success_count = 0
        valid_episodes = 0

        for i in range(batch_size):
            rewards = rewards_list[i]
            if not rewards:
                continue

            valid_episodes += 1
            total_reward += sum(rewards)
            if (
                batch_states[i].done
                and batch_states[i].current_node == batch_states[i].target_node
            ):
                success_count += 1

            R = 0
            returns = []
            for r in reversed(rewards):
                R = r + self.gamma * R
                returns.insert(0, R)

            returns_t = torch.tensor(returns, dtype=torch.float32, device=self.device)

            # 标准化 returns 增加训练稳定性
            if len(returns_t) > 1:
                returns_t = (returns_t - returns_t.mean()) / (returns_t.std() + 1e-8)

            policy_loss = 0.0
            value_loss = 0.0
            entropy_loss = 0.0

            for j in range(len(returns_t)):
                log_prob = log_probs_list[i][j]
                val = values_list[i][j]
                entropy = entropies_list[i][j]
                ret = returns_t[j]

                advantage = ret - val.item()
                policy_loss -= log_prob * advantage
                value_loss += F.smooth_l1_loss(
                    val, torch.tensor(ret, device=self.device)
                )
                entropy_loss -= entropy

            total_loss += (
                policy_loss + 0.5 * value_loss + self.entropy_coef * entropy_loss
            )

        if valid_episodes > 0:
            avg_reward = total_reward / valid_episodes
            success_rate = success_count / valid_episodes
            total_loss = total_loss / valid_episodes
        else:
            avg_reward = 0.0
            success_rate = 0.0
            total_loss = None

        return avg_reward, success_rate, total_loss
