"""
评估指标与指标统计库

专为 UAV 语义通信路由任务设计的评估函数库。
核心评估指标围绕 SNR (信噪比)、路由连通性与最短跳数展开。
"""

import numpy as np
import torch

from uav_semantic_planner.envs.environment import UAVRLEnvironment


def evaluate_navigation_metrics(
    model: torch.nn.Module,
    env: UAVRLEnvironment,
    eval_pairs: list[tuple[int, int]],
    node_embeddings: torch.Tensor,
    device: torch.device,
) -> dict[str, float]:
    """
    评估 RL 策略在 UAV 通信网络路由规划上的表现。

    Returns 字典包含:
        - success_rate: 成功寻找到目标节点的比例
        - avg_path_length: 成功路由的平均跳数
        - avg_bottleneck_snr: 成功路由的平均短板 SNR (木桶效应)
        - avg_snr_variance: 成功路由链路的平均 SNR 波动率
    """
    model.eval()

    total_samples = len(eval_pairs)
    if total_samples == 0:
        return {
            "success_rate": 0.0,
            "avg_path_length": 0.0,
            "avg_bottleneck_snr": 0.0,
            "avg_snr_variance": 0.0,
        }

    success_count = 0
    path_lengths = []
    bottleneck_snrs = []
    snr_variances = []

    with torch.no_grad():
        for start_node, target_node in eval_pairs:
            env.reset(start_node, target_node)

            # RNN 初始化
            path_memory = torch.zeros(1, model.gru_hidden_dim, device=device)
            target_emb = node_embeddings[target_node].unsqueeze(0).to(device)

            while not env.state.done:
                curr_node = env.state.current_node
                curr_emb = node_embeddings[curr_node].unsqueeze(0).to(device)

                valid_actions = env.get_valid_actions()
                if not valid_actions:
                    break

                neighbor_embs = node_embeddings[valid_actions].unsqueeze(0).to(device)
                neighbor_mask = torch.ones(
                    1, len(valid_actions), dtype=torch.float32, device=device
                )

                action_dist, _, next_memory = model(
                    current_emb=curr_emb,
                    target_emb=target_emb,
                    neighbor_embs=neighbor_embs,
                    path_memory=path_memory,
                    neighbor_mask=neighbor_mask,
                )

                if action_dist is None:
                    break

                # 评估时使用最大概率的确定性动作 (贪婪采样)
                best_action_idx = action_dist.logits.argmax(dim=-1).item()
                if best_action_idx >= len(valid_actions):
                    best_action_idx = 0
                chosen_action = valid_actions[best_action_idx]

                # 步进环境
                env.step(chosen_action)
                path_memory = next_memory

            if env.state.current_node == target_node:
                success_count += 1
                path_lengths.append(env.state.step_count)

                # 记录核心 SNR 状态
                bottleneck_snrs.append(
                    env.state.path_min_snr
                    if env.state.path_min_snr != float("inf")
                    else 0.0
                )
                if len(env.state.snr_history) > 1:
                    snr_variances.append(float(np.var(env.state.snr_history)))
                else:
                    snr_variances.append(0.0)

    # 汇总
    success_rate = success_count / total_samples
    avg_path_length = sum(path_lengths) / success_count if success_count > 0 else 0.0
    avg_bottleneck_snr = (
        sum(bottleneck_snrs) / success_count if success_count > 0 else 0.0
    )
    avg_snr_variance = sum(snr_variances) / success_count if success_count > 0 else 0.0

    return {
        "success_rate": success_rate,
        "avg_path_length": avg_path_length,
        "avg_bottleneck_snr": avg_bottleneck_snr,
        "avg_snr_variance": avg_snr_variance,
    }


def sample_uav_communication_pairs(
    env: UAVRLEnvironment,
    num_samples: int = 1000,
) -> list[tuple[int, int]]:
    """
    在通信拓扑上随机游走以收集可行的端到端通信对（用于训练）。

    使用图遍历来保证采样出的 (source, target) 在物理链路（受限于SNR）上至少有一条通路。
    """
    import random

    pairs = set()
    all_nodes = list(range(env.num_nodes))

    max_attempts = num_samples * 10
    attempts = 0

    while len(pairs) < num_samples and attempts < max_attempts:
        attempts += 1
        start_node = random.choice(all_nodes)

        # 使用 BFS 或随机游走寻找可行 target
        current = start_node
        visited = {current}
        path = [current]

        # 随机游走 3 - max_path_length 步
        steps = random.randint(3, min(10, env.max_path_length))

        for _ in range(steps):
            # 获取有效邻居 (必须考虑 SNR 阈值)
            env.reset(current, -1)  # target 设为假值
            env.state.visited = visited.copy()
            neighbors = env.get_valid_actions()

            if not neighbors:
                break

            next_node = random.choice(neighbors)
            visited.add(next_node)
            path.append(next_node)
            current = next_node

        if len(path) > 1:
            target_node = path[-1]
            if start_node != target_node:
                pairs.add((start_node, target_node))

    return list(pairs)
