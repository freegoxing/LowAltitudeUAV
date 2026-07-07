"""
评估工具模块

本模块封装了用于评估 RL 路径规划模型性能的核心函数，
包括路径搜索、MRR/Hits@N 指标计算等。
"""
import random
from collections import defaultdict, deque
from typing import List, Dict, Tuple, Set, Optional, TYPE_CHECKING

import numpy as np
import torch

if TYPE_CHECKING:
    from hgt_rl_planner.models import RLPolicyNet
    from hgt_rl_planner.environment import RLEnvironment


def has_path(start_node: int, end_node: int, adj: Dict[int, List[int]]) -> bool:
    """使用广度优先搜索 (BFS) 检查两个节点之间是否存在路径。"""
    if start_node == end_node:
        return True
    q = deque([start_node])
    visited = {start_node}
    while q:
        curr = q.popleft()
        if curr not in adj:
            continue
        for neighbor in adj[curr]:
            if neighbor == end_node:
                return True
            if neighbor not in visited:
                visited.add(neighbor)
                q.append(neighbor)
    return False


def evaluate_ranking_metrics_type_aware(
        model: 'RLPolicyNet',
        env: 'RLEnvironment',
        eval_pairs_positive: List[Tuple[int, int]],
        node_types: torch.Tensor,
        num_entities: int,
        node_embeddings: torch.Tensor,
        device: torch.device,
        num_candidate_neg_samples: int = 99,
        evaluation_seed: Optional[int] = None
) -> Dict[str, float]:
    """
    基于类型层次的排名指标评估（适用于 MOOCCubex 等教育知识图谱）。

    负采样策略：选择与真实目标**相同类型**但**不同节点**的实体作为负样本。
    这样可以测试模型在同类候选中识别正确目标的能力。

    Args:
        model: RL策略网络
        env: RL环境
        eval_pairs_positive: 正样本 (start_id, true_target_id) 对
        node_types: 节点类型张量
        num_entities: 实体总数
        node_embeddings: 节点嵌入
        device: 设备
        num_candidate_neg_samples: 每个正样本对应的负样本数量
        evaluation_seed: 评估随机种子

    Returns:
        包含 MRR 和 Hits@N 值的字典
    """
    model.eval()
    ranks = []

    if evaluation_seed is not None:
        rng = np.random.RandomState(evaluation_seed)
        random.seed(evaluation_seed)
    else:
        rng = np.random

    # 构建类型到节点ID的映射
    type_to_nodes = defaultdict(list)
    for node_id in range(len(node_types)):
        type_id = node_types[node_id].item()
        type_to_nodes[type_id].append(node_id)

    for idx, (start_id, true_target_id) in enumerate(eval_pairs_positive):
        candidate_targets = [true_target_id]

        # 获取真实目标的类型
        true_target_type = node_types[true_target_id].item()

        # 从同一类型中采样负样本
        same_type_nodes = type_to_nodes[true_target_type]

        # 过滤掉真实目标
        available_negatives = [n for n in same_type_nodes if n != true_target_id]

        # 采样负样本
        if not available_negatives:
            # 极端情况：该类型只有一个节点，没有负样本。这种情况下填充随机节点或略过。
            # 这里选择填充 true_target_id 以避免 crash，虽然这会降低指标但能保证程序运行。
            neg_samples = np.array([true_target_id] * num_candidate_neg_samples)
        elif len(available_negatives) >= num_candidate_neg_samples:
            neg_samples = rng.choice(available_negatives, num_candidate_neg_samples, replace=False)
        else:
            # 如果同类型节点不足，则重复采样
            neg_samples = rng.choice(available_negatives, num_candidate_neg_samples, replace=True)

        candidate_targets.extend(neg_samples.tolist())

        # 对所有候选进行评分
        target_scores = []
        for cand_id in candidate_targets:
            score, path_found = get_path_score(start_id, cand_id, model, env, node_embeddings, device)
            target_scores.append((cand_id, score, path_found))

        # 排序：优先成功路径，然后按分数
        target_scores.sort(key=lambda x: (x[2], x[1], -x[0]), reverse=True)

        # 找到真实目标的排名
        rank = -1
        for i, (cand_id, _, _) in enumerate(target_scores):
            if cand_id == true_target_id:
                rank = i + 1
                break

        if rank != -1:
            ranks.append(rank)
        else:
            ranks.append(num_candidate_neg_samples + 1)

    return calculate_mrr_hits(ranks)


def calculate_mrr_hits(ranks: List[int], hits_n: List[int] = [1, 3, 10]) -> Dict[str, float]:
    """
    计算 MRR 和 Hits@N 指标。
    Args:
        ranks: 真实目标在所有候选中的排名列表。
        hits_n: 列表，包含要计算的 Hits@N 值（例如 [1, 3, 10]）。
    Returns:
        包含 MRR 和 Hits@N 值的字典。
    """
    if not ranks:
        metrics = {f"hits@{n}": 0.0 for n in hits_n}
        metrics["mrr"] = 0.0
        return metrics

    # 计算 MRR
    mrr = np.mean([1.0 / rank for rank in ranks])

    # 计算 Hits@N
    metrics = {f"hits@{n}": np.mean([1 if rank <= n else 0 for rank in ranks]) for n in hits_n}
    metrics["mrr"] = mrr
    return metrics


def has_path_constrained(start_node: int, end_node: int, env: 'RLEnvironment', max_depth: int = 15) -> bool:
    """
    检查在当前环境约束(constraint_mode)下，从起点到终点是否存在逻辑通路。
    考虑了 visited 状态对 get_valid_actions() 的影响（简化版模拟）。
    """
    from hgt_rl_planner.environment import EpisodeState
    
    # 模拟环境状态
    initial_p = 0.0 # BFS 不依赖势能
    state = EpisodeState(start_node, end_node, initial_p)
    
    q = deque([(start_node, [start_node], {start_node})])
    visited_states = set() # (curr_node, frozenset(visited_nodes))
    
    while q:
        curr, path, visited = q.popleft()
        if curr == end_node:
            return True
        if len(path) > max_depth:
            continue
            
        # 构造临时状态以调用环境逻辑
        temp_state = EpisodeState(curr, end_node, 0.0)
        temp_state.path = path
        temp_state.visited = visited
        
        valid_actions = env.get_valid_actions(temp_state)
        
        for action in valid_actions:
            new_visited = visited | {action}
            state_key = (action, frozenset(new_visited))
            if state_key not in visited_states:
                visited_states.add(state_key)
                q.append((action, path + [action], new_visited))
                
    return False


def get_path_details(start_node_id: int,
                     end_node_id: int,
                     model: 'RLPolicyNet',
                     env: 'RLEnvironment',
                     node_embeddings: torch.Tensor,
                     device: torch.device) -> Tuple[List[int], float, bool, Dict]:
    """
    使用训练好的策略网络在两个节点之间寻找路径，并返回路径详情及诊断信息。
    """
    state = env.reset(start_node_id, end_node_id)
    path = [start_node_id]
    visited = {start_node_id}
    total_reward = 0
    done = False
    
    # 诊断统计
    path_info = {
        "total_p_skip": 0,
        "soft_edge_steps": 0,
        "prereq_satisfied": True
    }

    with torch.no_grad():
        path_memory = torch.zeros(1, model.gru_hidden_dim, device=device)
        for _ in range(env.max_path_length):
            valid_actions = env.get_valid_actions()
            if not valid_actions:
                break

            action_dist, _, path_memory = model(
                node_embeddings[state].unsqueeze(0),
                node_embeddings[end_node_id],
                node_embeddings[valid_actions],
                path_memory
            )

            if action_dist is None:
                break

            action_index = action_dist.probs.argmax().item()
            action = valid_actions[action_index]

            next_state, reward, done, step_info = env.step(action)
            
            # 记录诊断信息
            if step_info.get("is_soft_edge", False):
                path_info["soft_edge_steps"] += 1
            
            p_skip = step_info.get("p_skip", 0)
            if p_skip > 0:
                path_info["total_p_skip"] += p_skip

            path.append(next_state)
            visited.add(next_state)
            total_reward += reward
            state = next_state

            if done:
                # 记录终点先修状态
                path_info["prereq_satisfied"] = step_info.get("prereq_satisfied", True)
                break

    success = (path[-1] == end_node_id)
    return path, total_reward, success, path_info


def get_path_score(start_node_id: int,
                   target_node_id: int,
                   model: 'RLPolicyNet',
                   env: 'RLEnvironment',
                   node_embeddings: torch.Tensor,
                   device: torch.device) -> Tuple[float, bool]:
    """
    获取从起始节点到目标节点的路径分数（总奖励）和是否成功。
    """
    _, total_reward, success, _ = get_path_details(start_node_id, target_node_id, model, env, node_embeddings, device)
    return total_reward, success


def evaluate_ranking_metrics(
        model: 'RLPolicyNet',
        env: 'RLEnvironment',
        eval_pairs_positive: List[Tuple[int, int]],
        all_known_triplets: Optional[Set[Tuple[int, int, int]]],  # For filtered ranking in standard datasets
        adj: Dict[int, List[int]],  # For has_path filtering
        num_entities: int,
        node_embeddings: torch.Tensor,
        device: torch.device,
        num_candidate_neg_samples: int = 99,  # 1 true + num_candidate_neg_samples false
        evaluation_seed: Optional[int] = None  # [新增] 评估随机种子，确保负采样确定性
) -> Dict[str, float]:
    """
    对模型进行排名指标评估 (MRR, Hits@N)。
    Args:
        model: RL策略网络。
        env: RL环境。
        eval_pairs_positive: 正样本 (start_id, true_target_id) 对。
        all_known_triplets: 所有已知的三元组，用于Filtered Ranking。
        adj: 评估图的邻接列表，用于判断路径连通性。
        num_entities: 实体总数。
        node_embeddings: 节点嵌入。
        device: 设备。
        num_candidate_neg_samples: 每个正样本对应的负样本数量。
    Returns:
        包含 MRR 和 Hits@N 值的字典。
    """
    model.eval()
    ranks = []

    # [修复] 设置评估随机种子以确保负采样的确定性
    if evaluation_seed is not None:
        rng = np.random.RandomState(evaluation_seed)
        random.seed(evaluation_seed)
    else:
        rng = np.random

    # 获取所有实体ID列表，用于负采样
    all_entity_ids = list(range(num_entities))

    for idx, (start_id, true_target_id) in enumerate(eval_pairs_positive):
        candidate_targets = []
        candidate_targets.append(true_target_id)  # 添加真实目标

        # 生成负样本
        neg_samples_generated = 0
        attempts = 0
        max_attempts = num_candidate_neg_samples * 10  # 避免无限循环

        while neg_samples_generated < num_candidate_neg_samples and attempts < max_attempts:
            # [修复] 使用确定性随机数生成器进行负样本采样
            if evaluation_seed is not None:
                false_target_id = int(rng.choice(all_entity_ids))
            else:
                false_target_id = random.choice(all_entity_ids)

            # 确保负样本不是真实目标
            if false_target_id == true_target_id:
                attempts += 1
                continue

            # 针对标准数据集，如果 false_target_id 曾经在训练/验证/测试集中与 start_id 形成过任何关系 (h,r,t)，则过滤
            # 符合标准的 Filtered Ranking 逻辑
            if all_known_triplets:
                found_known_relation = False
                for r_idx in range(len(env.relation_map)):  # 使用 env.relation_map 的长度获取关系总数
                    if (start_id, r_idx, false_target_id) in all_known_triplets:
                        found_known_relation = True
                        break
                if found_known_relation:
                    attempts += 1
                    continue
            
            # [修复] 使用 adj 进一步过滤。如果在 KG 邻接表中 false_target_id 已经是 start_id 的直接后继，
            # 则在排名任务中将其视为“已知正向关系”而过滤掉，以保证负样本的纯净度。
            if adj and start_id in adj and false_target_id in adj[start_id]:
                attempts += 1
                continue

            candidate_targets.append(false_target_id)
            neg_samples_generated += 1
            attempts += 1

        if neg_samples_generated < num_candidate_neg_samples:
            # 如果未能生成足够多的负样本，发出警告或调整策略
            print(
                f"警告: 为 ({start_id}, {true_target_id}) 生成的负样本不足 ({neg_samples_generated}/{num_candidate_neg_samples})")

        # 对所有候选目标进行评分
        target_scores = []  # 存储 (target_id, score, path_found)
        for cand_target_id in candidate_targets:
            score, path_found = get_path_score(start_id, cand_target_id, model, env, node_embeddings, device)
            target_scores.append((cand_target_id, score, path_found))

        # 排序: 优先成功路径，其次是高分，最后是节点ID (保持确定性)
        # 注意: 如果path_found为False，score可能为0或负数。为了排名准确，成功路径应该总是排在失败路径之前。
        target_scores.sort(key=lambda x: (x[2], x[1], -x[0]),
                           reverse=True)  # x[2] (path_found) True>False, x[1] (score) High->Low, -x[0] (target_id) Low->High for deterministic tie-break

        # 找到真实目标的排名
        rank = -1
        for i, (cand_id, _, _) in enumerate(target_scores):
            if cand_id == true_target_id:
                rank = i + 1
                break

        if rank != -1:
            ranks.append(rank)
        else:
            # 如果真实目标未被列入排名 (理论上不应发生，因为已明确添加)
            # 或者未成功找到路径导致分数过低排名非常靠后
            # 可以考虑将其排名设置为 num_candidate_neg_samples + 1 或 num_entities
            # 为了MRR/Hits@N的计算，假设它排在所有负样本之后
            ranks.append(num_candidate_neg_samples + 1)

    return calculate_mrr_hits(ranks)


def _normalize_prerequisite_map(
    prerequisite_map: Dict[int, Set[int]],
) -> Dict[int, Set[int]]:
    normalized: Dict[int, Set[int]] = {}
    for target, prereqs in prerequisite_map.items():
        normalized[int(target)] = {int(prereq) for prereq in prereqs}
    return normalized


def _is_prereq_ancestor(
    ancestor: int,
    node: int,
    prerequisite_map: Dict[int, Set[int]],
    memo: Dict[Tuple[int, int], bool],
    visiting: Optional[Set[Tuple[int, int]]] = None,
) -> bool:
    key = (int(ancestor), int(node))
    if key in memo:
        return memo[key]
    if visiting is None:
        visiting = set()
    if key in visiting:
        # 先修图中若仍残留环，评估阶段将其视为“无法证明 ancestor 是合法上游”，
        # 以避免递归爆栈并保持指标可计算。
        memo[key] = False
        return False

    visiting.add(key)

    node_prereqs = prerequisite_map.get(int(node), set())
    if int(ancestor) in node_prereqs:
        visiting.discard(key)
        memo[key] = True
        return True

    result = any(
        _is_prereq_ancestor(
            int(ancestor),
            int(parent),
            prerequisite_map,
            memo,
            visiting,
        )
        for parent in node_prereqs
    )
    visiting.discard(key)
    memo[key] = result
    return result


def _get_backbone_frontier_prereqs(
    target_node: int,
    prerequisite_map: Dict[int, Set[int]],
    memo: Dict[Tuple[int, int], bool],
) -> Set[int]:
    direct_prereqs = set(prerequisite_map.get(int(target_node), set()))
    if len(direct_prereqs) <= 1:
        return direct_prereqs

    # 仅保留最靠近 target 的主干锚点，去掉被其他 direct prereq 覆盖的上游祖先。
    frontier = set(direct_prereqs)
    for prereq in direct_prereqs:
        for other in direct_prereqs:
            if prereq == other:
                continue
            if _is_prereq_ancestor(int(prereq), int(other), prerequisite_map, memo):
                frontier.discard(int(prereq))
                break
    return frontier or direct_prereqs


def compute_path_prereq_metrics(
    path: List[int], prerequisite_map: Dict[int, Set[int]], target_node: int
) -> Dict[str, float]:
    """
    计算贴合“骨架+血肉”论文设想的多项指标。

    1. path_prereq_compliance_rate (PPC):
       只检查路径中实际访问到的主干节点顺序是否违背先修 DAG。

    2. target_prereq_coverage_ratio (TFC):
       检查 target 最近一层的主干锚点先修（frontier prereqs）在到达 target 前是否被覆盖。

    3. target_relevant_ppc:
       只在 target 的祖先闭包里统计顺序一致性，不再拿整条路径上的所有主干节点做分母。

    4. frontier_hit_rate:
       成功路径中，至少命中一个目标关键先修锚点 (frontier) 的比例。

    5. conditional_tfc:
       只对“目标确实有 frontier 且路径触达过相关主干 (target ancestors)”的样本统计覆盖率。
    """
    normalized_map = _normalize_prerequisite_map(prerequisite_map)
    ancestor_memo: Dict[Tuple[int, int], bool] = {}
    target_id = int(target_node)

    # 获取 target 的所有主干祖先节点 (用于 target_relevant_ppc 和 conditional_tfc)
    def get_all_ancestors(node_id: int, visited: Set[int]) -> Set[int]:
        ancestors = set()
        for p in normalized_map.get(node_id, []):
            if p not in visited:
                visited.add(p)
                ancestors.add(p)
                ancestors.update(get_all_ancestors(p, visited))
        return ancestors

    all_target_ancestors = get_all_ancestors(target_id, set())

    backbone_nodes = set(normalized_map.keys())
    for prereqs in normalized_map.values():
        backbone_nodes.update(prereqs)

    backbone_path = [int(node) for node in path if int(node) in backbone_nodes]

    # --- 1. PPC (原有指标) ---
    ordered_backbone_pairs = 0
    consistent_backbone_pairs = 0
    for i, earlier in enumerate(backbone_path):
        for later in backbone_path[i + 1:]:
            if _is_prereq_ancestor(later, earlier, normalized_map, ancestor_memo):
                ordered_backbone_pairs += 1
            elif _is_prereq_ancestor(earlier, later, normalized_map, ancestor_memo):
                ordered_backbone_pairs += 1
                consistent_backbone_pairs += 1

    ppc = (
        consistent_backbone_pairs / ordered_backbone_pairs
        if ordered_backbone_pairs > 0
        else 1.0
    )

    # --- 2. Target-Relevant PPC (新指标) ---
    relevant_backbone_path = [n for n in backbone_path if n in all_target_ancestors or n == target_id]
    rel_ordered_pairs = 0
    rel_consistent_pairs = 0
    for i, earlier in enumerate(relevant_backbone_path):
        for later in relevant_backbone_path[i + 1:]:
            if _is_prereq_ancestor(later, earlier, normalized_map, ancestor_memo):
                rel_ordered_pairs += 1
            elif _is_prereq_ancestor(earlier, later, normalized_map, ancestor_memo):
                rel_ordered_pairs += 1
                rel_consistent_pairs += 1
    
    target_relevant_ppc = (
        rel_consistent_pairs / rel_ordered_pairs
        if rel_ordered_pairs > 0
        else 1.0
    )

    # --- 3. TFC & Frontier Hit (原有指标增强) ---
    target_frontier_prereqs = _get_backbone_frontier_prereqs(
        target_id, normalized_map, ancestor_memo
    )
    
    # 路径中在 target 之前访问过的节点
    visited_in_path = set(int(n) for n in path[:-1])
    
    if not target_frontier_prereqs:
        tfc = 1.0
        frontier_hit = 1.0
        conditional_tfc = None  # 稍后处理
    else:
        covered_count = sum(1 for prereq in target_frontier_prereqs if int(prereq) in visited_in_path)
        tfc = covered_count / len(target_frontier_prereqs)
        frontier_hit = 1.0 if covered_count > 0 else 0.0
        
        # --- 4. Conditional TFC (新指标) ---
        # 只有当路径触达过 target 的相关祖先主干时，才计入统计
        if any(n in all_target_ancestors for n in backbone_path):
            conditional_tfc = tfc
        else:
            conditional_tfc = None

    return {
        "ppc": ppc,
        "tfc": tfc,
        "target_relevant_ppc": target_relevant_ppc,
        "frontier_hit_rate": frontier_hit,
        "conditional_tfc": conditional_tfc
    }



def evaluate_navigation_metrics(
        model: 'RLPolicyNet',
        env: 'RLEnvironment',
        eval_pairs: List[Tuple[int, int]],
        node_embeddings: torch.Tensor,
        device: torch.device,
        metric_prerequisite_map: Optional[Dict[int, Set[int]]] = None,
) -> Dict[str, float]:
    """
    计算增强后的导航指标。
    """
    model.eval()
    success_count = 0
    total_path_len = 0
    
    compliance_rates = []
    coverage_ratios = []
    target_relevant_ppcs = []
    frontier_hit_rates = []
    conditional_tfcs = []
    
    if not eval_pairs:
        return {
            "success_rate": 0.0, 
            "avg_path_length": 0.0,
            "path_prereq_compliance": 0.0,
            "target_frontier_coverage": 0.0,
            "target_relevant_ppc": 0.0,
            "frontier_hit_rate": 0.0,
            "conditional_tfc": 0.0,
        }

    for start_node, target_node in eval_pairs:
        path, _, success, info = get_path_details(start_node, target_node, model, env, node_embeddings, device)
        
        steps_in_this_path = len(path) - 1

        if success:
            success_count += 1
            total_path_len += steps_in_this_path
            
            # 计算教育学路径质量指标 (仅对成功路径计算)
            if metric_prerequisite_map:
                metrics = compute_path_prereq_metrics(path, metric_prerequisite_map, target_node)
                compliance_rates.append(metrics["ppc"])
                coverage_ratios.append(metrics["tfc"])
                target_relevant_ppcs.append(metrics["target_relevant_ppc"])
                frontier_hit_rates.append(metrics["frontier_hit_rate"])
                if metrics["conditional_tfc"] is not None:
                    conditional_tfcs.append(metrics["conditional_tfc"])

    success_rate = success_count / len(eval_pairs)
    avg_path_length = total_path_len / max(success_count, 1) if success_count > 0 else 0.0
    
    return {
        "success_rate": success_rate,
        "avg_path_length": avg_path_length,
        "path_prereq_compliance": float(np.mean(compliance_rates)) if compliance_rates else 0.0,
        "target_frontier_coverage": float(np.mean(coverage_ratios)) if coverage_ratios else 0.0,
        "target_relevant_ppc": float(np.mean(target_relevant_ppcs)) if target_relevant_ppcs else 0.0,
        "frontier_hit_rate": float(np.mean(frontier_hit_rates)) if frontier_hit_rates else 0.0,
        "conditional_tfc": float(np.mean(conditional_tfcs)) if conditional_tfcs else 0.0,
    }


def sample_curriculum_pairs_by_constrained_walk(
        env: 'RLEnvironment',
        num_samples: int = 100,
        seed: int = 42
) -> List[Tuple[int, int]]:
    """
    通过在当前环境约束下进行随机游走来采样训练对。
    这能生成一系列在当前规则下“合法可达”但可能包含多步探索的认知路径。
    """
    import random
    random.seed(seed)
    
    reachable_pairs = set()
    # 直接使用节点数量构造 ID 列表，不再依赖 node_map 的值类型
    num_nodes = getattr(env, 'num_nodes', len(env.node_map))
    if num_nodes <= 1:
        return []
    nodes = list(range(num_nodes))
    
    attempts = 0
    while len(reachable_pairs) < num_samples and attempts < num_samples * 20:
        attempts += 1
        start = random.choice(nodes)
        
        # 模拟一次短程随机游走 (4-10步)
        curr = start
        visited = {start}
        path = [start]
        
        from hgt_rl_planner.environment import EpisodeState
        for _ in range(random.randint(4, 10)):
            # 临时状态用于获取动作
            temp_state = EpisodeState(curr, -1, 0.0) 
            temp_state.path = path
            temp_state.visited = visited
            
            valid_actions = env.get_valid_actions(temp_state)
            if not valid_actions: break
            
            curr = random.choice(valid_actions)
            visited.add(curr)
            path.append(curr)
            
        if len(path) >= 4:
            reachable_pairs.add((start, path[-1]))
            
    return list(reachable_pairs)


def evaluate_model_checkpoint(
        model: 'RLPolicyNet',
        env: 'RLEnvironment',
        eval_pairs_positive: List[Tuple[int, int]],
        adj: Dict[int, List[int]],  # 新增: 传入邻接表
        num_entities: int,  # 新增: 传入实体总数
        node_embeddings: torch.Tensor,
        device: torch.device,
        all_known_triplets: Optional[Set[Tuple[int, int, int]]] = None,  # 新增: 传入所有已知三元组，用于Filtered Ranking
        num_candidate_neg_samples: int = 99,  # 新增: 传入排名评估的负样本数量
        use_type_aware_ranking: bool = False,  # 新增: 是否使用类型感知的排名评估
        node_types: Optional[torch.Tensor] = None,  # 新增: 节点类型（用于类型感知排名）
        seed: int = 42,  # 随机种子
        metric_prerequisite_map: Optional[Dict[int, Set[int]]] = None,
) -> Dict[str, float]:
    """
    对单个模型检查点进行全方位评估。
    包含:
    1. Navigation Metrics (Success Rate, Path Length) - 教育场景核心指标
    2. Ranking Metrics (MRR, Hits@N) - 学术对比指标 (可选)
    """
    model.eval()

    # 1. 计算核心导航指标
    nav_metrics = evaluate_navigation_metrics(
        model,
        env,
        eval_pairs_positive,
        node_embeddings,
        device,
        metric_prerequisite_map=metric_prerequisite_map,
    )

    # 2. 计算学术排名指标 (1 vs Negatives)
    # 注意: 这对于 Point-to-Point 模型比较慢，因为要运行 N+1 次 Agent
    # 如果为了速度，可以注释掉下面这块，或者减少负样本数量

    if use_type_aware_ranking and node_types is not None:
        # 使用类型感知的排名评估（推荐用于 MOOCCubex）
        ranking_metrics = evaluate_ranking_metrics_type_aware(
            model=model,
            env=env,
            eval_pairs_positive=eval_pairs_positive,
            node_types=node_types,
            num_entities=num_entities,
            node_embeddings=node_embeddings,
            device=device,
            num_candidate_neg_samples=num_candidate_neg_samples,
            evaluation_seed=seed
        )
    else:
        # 使用标准的排名评估（适用于标准知识图谱）
        ranking_metrics = evaluate_ranking_metrics(
            model=model,
            env=env,
            eval_pairs_positive=eval_pairs_positive,
            all_known_triplets=all_known_triplets,
            adj=adj,
            num_entities=num_entities,
            node_embeddings=node_embeddings,
            device=device,
            num_candidate_neg_samples=num_candidate_neg_samples,
            evaluation_seed=seed,
        )

    # 合并结果返回
    return {**nav_metrics, **ranking_metrics}


def analyze_learning_path_quality(
        paths: List[List[int]],
        node_types: Optional[torch.Tensor] = None,
        type_names: Optional[List[str]] = None
) -> Dict[str, any]:
    """
    分析学习路径的质量，包括概念类型分布等。
    Args:
        paths: 路径列表，每个路径是节点ID的列表
        node_types: 节点类型张量，shape=[num_nodes, num_types]
        type_names: 类型名称列表，如 ["Theory", "Method", "Application", "Tool"]
    Returns:
        包含路径质量分析的字典
    """
    if not paths:
        return {}

    analysis = {}

    # 基本统计
    path_lengths = [len(path) - 1 for path in paths]  # 边的数量
    analysis["avg_path_length"] = np.mean(path_lengths)
    analysis["min_path_length"] = np.min(path_lengths)
    analysis["max_path_length"] = np.max(path_lengths)
    analysis["std_path_length"] = np.std(path_lengths)

    # 概念类型分布分析
    if node_types is not None and type_names is not None:
        num_types = len(type_names)
        type_distributions = []
        for path in paths:
            if len(path) == 0:
                continue
            
            # 获取路径中各节点的类型 ID
            path_node_types = node_types[path]
            
            # 统计各类型出现的次数
            type_counts = np.zeros(num_types)
            for t_id in path_node_types.tolist():
                if 0 <= t_id < num_types:
                    type_counts[int(t_id)] += 1
            
            type_percentages = type_counts / len(path)
            type_distributions.append(type_percentages)

        if type_distributions:
            avg_type_dist = np.mean(type_distributions, axis=0)
            analysis["type_distribution"] = {
                name: float(avg_type_dist[i]) for i, name in enumerate(type_names)
            }

    return analysis


def evaluate_prerequisite_compliance(
        paths: List[List[int]],
        prerequisite_map: Dict[int, Set[int]]
) -> Dict[str, float]:
    """
    评估路径的先修关系合规性。
    Args:
        paths: 路径列表
        prerequisite_map: 先修关系映射 {concept: {prerequisites}}
    Returns:
        包含先修合规率等指标的字典
    """
    if not paths or not prerequisite_map:
        return {"compliance_rate": 0.0, "violation_count": 0}

    total_violations = 0
    total_checks = 0

    for path in paths:
        if len(path) < 2:
            continue

        # 检查路径中的每个节点是否满足其先修条件
        visited = set()
        for i, node in enumerate(path):
            visited.add(node)

            # 检查当前节点的所有先修要求
            if node in prerequisite_map:
                prerequisites = prerequisite_map[node]
                for prereq in prerequisites:
                    total_checks += 1
                    # 检查先修节点是否在路径中的前面部分（已访问）
                    if prereq not in visited:
                        total_violations += 1

    if total_checks == 0:
        return {"compliance_rate": 1.0, "violation_count": 0}

    compliance_rate = 1.0 - (total_violations / total_checks)
    return {
        "compliance_rate": compliance_rate,
        "violation_count": total_violations,
        "total_checks": total_checks
    }


def evaluate_path_diversity(
        paths: List[List[int]]
) -> Dict[str, float]:
    """
    评估路径的多样性，使用 Jaccard 相似度等指标。
    Args:
        paths: 路径列表
    Returns:
        包含多样性指标的字典
    """
    if len(paths) < 2:
        return {"avg_jaccard_similarity": 0.0, "unique_path_ratio": 1.0}

    # 计算所有路径对的 Jaccard 相似度
    jaccard_similarities = []
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            set_i = set(paths[i])
            set_j = set(paths[j])

            if len(set_i) == 0 and len(set_j) == 0:
                similarity = 1.0
            else:
                intersection = len(set_i & set_j)
                union = len(set_i | set_j)
                similarity = intersection / union if union > 0 else 0.0

            jaccard_similarities.append(similarity)

    avg_jaccard = np.mean(jaccard_similarities) if jaccard_similarities else 0.0

    # 计算唯一路径比例（完全不同的路径）
    unique_paths = set(tuple(path) for path in paths)
    unique_path_ratio = len(unique_paths) / len(paths) if paths else 0.0

    return {
        "avg_jaccard_similarity": avg_jaccard,
        "unique_path_ratio": unique_path_ratio,
        "total_paths": len(paths),
        "unique_paths": len(unique_paths)
    }


def evaluate_educational_metrics(
        model: 'RLPolicyNet',
        env: 'RLEnvironment',
        eval_pairs: List[Tuple[int, int]],
        node_embeddings: torch.Tensor,
        node_types: Optional[torch.Tensor] = None,
        type_names: Optional[List[str]] = None,
        device: torch.device = None
) -> Dict[str, any]:
    """
    综合评估教育学指标，包括导航指标、路径质量、先修合规性和多样性。
    Args:
        model: RL策略网络
        env: RL环境
        eval_pairs: 评估样本对
        node_embeddings: 节点嵌入
        node_types: 节点类型张量
        type_names: 类型名称列表
        device: 设备
    Returns:
        包含所有教育学评估指标的字典
    """
    model.eval()

    # 1. 获取所有路径
    all_paths = []
    success_count = 0

    for start_node, target_node in eval_pairs:
        path, _, success, info = get_path_details(
            start_node, target_node, model, env, node_embeddings, device
        )
        all_paths.append(path)
        if success:
            success_count += 1

    # 2. 基础导航指标
    total_path_len = sum(len(path) - 1 for path in all_paths if len(path) > 1)
    success_rate = success_count / len(eval_pairs) if eval_pairs else 0.0
    avg_path_length = total_path_len / max(success_count, 1) if success_count > 0 else 0.0

    metrics = {
        "success_rate": success_rate,
        "avg_path_length": avg_path_length,
        "num_evaluated_pairs": len(eval_pairs),
        "num_successful_paths": success_count
    }

    # 3. 学习路径质量分析
    path_quality = analyze_learning_path_quality(
        [path for path in all_paths if len(path) > 1],
        node_types,
        type_names
    )
    metrics.update({f"path_quality_{k}": v for k, v in path_quality.items()})

    # 4. 先修合规性分析
    if hasattr(env, 'prerequisite_map') and env.prerequisite_map:
        compliance = evaluate_prerequisite_compliance(
            [path for path in all_paths if len(path) > 1],
            env.prerequisite_map
        )
        metrics.update({f"prereq_{k}": v for k, v in compliance.items()})

    # 5. 路径多样性分析
    diversity = evaluate_path_diversity(
        [path for path in all_paths if len(path) > 1]
    )
    metrics.update({f"diversity_{k}": v for k, v in diversity.items()})

    return metrics
