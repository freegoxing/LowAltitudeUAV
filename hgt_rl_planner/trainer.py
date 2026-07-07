"""
强化学习训练逻辑模块

实现对应的训练器 (RLTrainer)，专门适配大规模异构教育图谱。
"""

import logging
from typing import List, Dict, Tuple

import numpy as np
import torch
import torch.nn.functional as F

from .models import RLPolicyNet
from .environment import RLEnvironment

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RLTrainer:
    def __init__(self, environment: RLEnvironment, model: RLPolicyNet, node_embeddings: torch.Tensor,
                 device: torch.device, learning_rate: float = 0.001):
        self.env = environment
        self.model = model
        self.node_embeddings = node_embeddings
        self.device = device
        self.optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        self.gamma = 0.99
        self.entropy_coeff = 0.01
        
        logging.info(f"RLTrainer initialized with device: {self.device}")

    def _get_base_model(self):
        """处理 DDP 包装情况，获取原始模型"""
        if hasattr(self.model, 'module'):
            return self.model.module
        return self.model

    def train_episode(self, start_node: int, target_node: int) -> Tuple[float, int, bool, torch.Tensor]:
        """保留单实例训练，用于兼容旧代码或小规模调试"""
        self.model.train()
        base_model = self._get_base_model()
        state = self.env.reset(start_node, target_node)
        log_probs, values, rewards, entropies = [], [], [], []
        hidden = torch.zeros(1, base_model.gru_hidden_dim, device=self.device)

        for _ in range(self.env.max_path_length):
            valid_actions = self.env.get_valid_actions()
            if not valid_actions: break

            current_emb = self.node_embeddings[state].unsqueeze(0).to(self.device)
            target_emb = self.node_embeddings[target_node].to(self.device)
            neighbor_embs = self.node_embeddings[valid_actions].to(self.device)

            # 调用已升级的 batch-ready 模型 (batch_size=1)
            action_dist, value, next_hidden = self.model(
                current_emb, target_emb, neighbor_embs.unsqueeze(0), hidden, None
            )
            hidden = next_hidden

            if action_dist is None: break

            action_idx = action_dist.sample()
            action = valid_actions[action_idx.item()]

            next_state, reward, done, _ = self.env.step(action)
            
            log_probs.append(action_dist.log_prob(action_idx))
            values.append(value)
            rewards.append(reward)
            entropies.append(action_dist.entropy())

            state = next_state
            if done: break

        if not rewards: return 0, 0, False, None
        return self._compute_loss(rewards, values, log_probs, entropies)

    def _compute_loss(self, rewards, values, log_probs, entropies):
        """计算 A2C 损失"""
        returns, R = [], 0
        for r in reversed(rewards):
            R = r + self.gamma * R
            returns.insert(0, R)
        
        returns = torch.tensor(returns, device=self.device)
        values_tensor = torch.cat(values).view(-1)
        log_probs_tensor = torch.stack(log_probs).view(-1)
        entropies_tensor = torch.stack(entropies).view(-1)

        advantages = returns - values_tensor.detach()
        policy_loss = -(log_probs_tensor * advantages).mean()
        value_loss = F.mse_loss(values_tensor, returns)
        entropy_loss = -self.entropy_coeff * entropies_tensor.mean()

        return sum(rewards), len(rewards), True, policy_loss + value_loss + entropy_loss

    def train_batch(self, batch_pairs: List[Tuple[int, int]]) -> Tuple[float, float, torch.Tensor]:
        """
        真正的批量训练函数：同时推进多个 Episode，释放 GPU 算力。
        """
        self.model.train()
        base_model = self._get_base_model()
        batch_size = len(batch_pairs)
        
        # 1. 初始化 batch 状态
        batch_states = self.env.reset_batch(batch_pairs, self.device)
        
        # 提取当前节点和目标节点
        states = torch.tensor([s.current_node for s in batch_states], device=self.device)
        target_nodes = torch.tensor([s.target_node for s in batch_states], device=self.device)
        hiddens = torch.zeros(batch_size, base_model.gru_hidden_dim, device=self.device)
        
        # 轨迹存储
        batch_log_probs = [[] for _ in range(batch_size)]
        batch_values = [[] for _ in range(batch_size)]
        batch_rewards = [[] for _ in range(batch_size)]
        batch_entropies = [[] for _ in range(batch_size)]
        # 记录真实导航成功率（是否到达 target），避免与“可反传样本占比”混淆
        batch_success = [False for _ in range(batch_size)]

        for _ in range(self.env.max_path_length):
            if all(s.done for s in batch_states): break
            
            # 2. 收集有效邻居
            batch_valid_actions = []
            max_neighbors = 0
            for i in range(batch_size):
                if batch_states[i].done:
                    batch_valid_actions.append([])
                    continue
                actions = self.env.get_valid_actions(batch_states[i])
                batch_valid_actions.append(actions)
                max_neighbors = max(max_neighbors, len(actions))
            
            if max_neighbors == 0: break

            # 3. 批量决策
            neighbor_embs = torch.zeros(batch_size, max_neighbors, self.node_embeddings.size(1), device=self.device)
            neighbor_mask = torch.zeros(batch_size, max_neighbors, device=self.device)
            for i, actions in enumerate(batch_valid_actions):
                if actions:
                    num_a = len(actions)
                    neighbor_embs[i, :num_a] = self.node_embeddings[actions]
                    neighbor_mask[i, :num_a] = 1

            current_embs = self.node_embeddings[states]
            target_embs = self.node_embeddings[target_nodes]
            action_dist, state_values, next_hiddens = self.model(
                current_embs, target_embs, neighbor_embs, hiddens, neighbor_mask
            )
            hiddens = next_hiddens

            # 4. 执行动作
            actions_to_take = action_dist.sample()
            actions_cpu = actions_to_take.cpu().numpy()
            
            next_nodes_list = []
            for i, act_idx in enumerate(actions_cpu):
                if not batch_states[i].done and act_idx < len(batch_valid_actions[i]):
                    next_nodes_list.append(batch_valid_actions[i][act_idx])
                else:
                    next_nodes_list.append(0)
            
            next_nodes_tensor = torch.tensor(next_nodes_list, device=self.device)
            next_embs = self.node_embeddings[next_nodes_tensor]
            potentials = torch.cosine_similarity(next_embs, target_embs, eps=1e-8).detach().cpu().numpy()
            
            final_actions = [
                next_nodes_list[i] if (not batch_states[i].done and actions_cpu[i] < len(batch_valid_actions[i])) else None
                for i in range(batch_size)
            ]
            
            step_results = self.env.step_batch(batch_states, final_actions, potentials)
            
            # 5. 记录数据
            all_log_probs = action_dist.log_prob(actions_to_take)
            all_entropies = action_dist.entropy()

            for i, (reward, done, info) in enumerate(step_results):
                if final_actions[i] is None: continue
                batch_log_probs[i].append(all_log_probs[i:i+1])
                batch_values[i].append(state_values[i])
                batch_rewards[i].append(reward)
                batch_entropies[i].append(all_entropies[i])
                if info.get("status") == "success":
                    batch_success[i] = True
                states[i] = batch_states[i].current_node

        # 6. 计算 Batch Loss
        total_loss = None
        valid_episodes = 0
        for i in range(batch_size):
            if not batch_rewards[i]: continue
            _, _, _, loss = self._compute_loss(batch_rewards[i], batch_values[i], batch_log_probs[i], batch_entropies[i])
            if total_loss is None:
                total_loss = loss
            else:
                total_loss = total_loss + loss
            valid_episodes += 1
            
        success_rate = sum(batch_success) / max(1, batch_size)
        
        final_loss = total_loss / max(1, valid_episodes) if total_loss is not None else None
        
        return (
            sum([sum(r) for r in batch_rewards]) / batch_size,
            success_rate,
            final_loss,
        )

    def train(self, training_pairs, num_episodes, batch_size=64, print_every=100, save_every=500, model_save_dir='./checkpoints/'):
        """
        高性能训练主循环 (兼容旧接口 V2.8)
        """
        total_rewards, total_srs = [], []
        num_batches = max(1, num_episodes // batch_size)

        logging.info(f"Starting Training: {num_episodes} Episodes | Batch Size: {batch_size} | Updates: {num_batches}")

        for b in range(num_batches):
            # 随机采样一个 batch 的对
            batch_idx = np.random.choice(len(training_pairs), batch_size)
            batch_data = [training_pairs[i] for i in batch_idx]

            # 内部调用已优化的 train_batch
            avg_reward, sr, loss = self.train_batch(batch_data)
            
            # 更新优化器
            if loss is not None and isinstance(loss, torch.Tensor):
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                self.optimizer.step()

            total_rewards.append(avg_reward)
            total_srs.append(sr)

            # print_every 是 episode 数，换算成 batch 数作为触发频率和统计窗口
            batches_per_print = max(1, print_every // batch_size)
            if (b + 1) % batches_per_print == 0:
                avg_r = np.mean(total_rewards[-batches_per_print:])
                avg_sr = np.mean(total_srs[-batches_per_print:])
                logging.info(f"Batch {b+1}/{num_batches} | Avg Reward (Last {print_every} Ep): {avg_r:.2f} | Avg SR: {avg_sr:.2%}")

