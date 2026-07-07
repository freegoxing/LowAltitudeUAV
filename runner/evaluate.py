"""
MOOCCubex 学术评估脚本 (V3.0 - 修复评估指标)
使用正确的评估实现，支持学术模式和实用模式
"""

import argparse
import json
import os
import random
import sys
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

import matplotlib.pyplot as plt
import numpy as np
import torch

from hgt_rl_planner.data_loader import (
    load_custom_kg_from_json,
    load_mooccubex_subgraph,
)
from hgt_rl_planner.evaluation_lib import (
    evaluate_model_checkpoint,
    evaluate_navigation_metrics,
    evaluate_ranking_metrics_type_aware,
)
from hgt_rl_planner.models import RLPolicyNet
from hgt_rl_planner.environment import RLEnvironment
from hgt_rl_planner.utils.data_processing import process_custom_kg
from hgt_rl_planner.utils.plotting import (
    plot_aggregated_metric_over_time,
    plot_metric_over_time,
    plot_metrics_summary,
)
from hgt_rl_planner.utils.seeding import set_seed


def _print_flush(message: str) -> None:
    print(message, flush=True)


def _has_bounded_path(
    start_node: int,
    end_node: int,
    adj: Dict[int, List[int]],
    max_depth: int,
) -> bool:
    """使用节点级有界 BFS 检查路径是否存在，避免状态空间爆炸。"""
    if start_node == end_node:
        return True

    queue = deque([(start_node, 0)])
    visited = {start_node}

    while queue:
        curr, depth = queue.popleft()
        if depth >= max_depth:
            continue

        for nxt in adj.get(curr, []):
            if nxt == end_node:
                return True
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, depth + 1))

    return False

def summarize_eval_samples(
    eval_samples: List[Tuple[int, int]],
    prereq_map: Dict[int, Set[int]],
    node_types: torch.Tensor,
    env: RLEnvironment = None,
    max_path_length: int = 15,
) -> None:
    """打印评估样本统计：类型分布、先修连通性及全图（Hybrid）连通性。"""
    if not eval_samples:
        _print_flush("--- Eval Sample Summary: no samples ---")
        return

    # 1. 构建先修邻接 (用于硬约束检查)
    prereq_adj = defaultdict(list)
    for tgt, srcs in prereq_map.items():
        for src in srcs:
            prereq_adj[src].append(tgt)

    # 2. 构建全图邻接 (用于 Hybrid 连通性检查)
    full_adj = defaultdict(list)
    if env:
        for src, neighbors in env.adjacency_list.items():
            for tgt, _ in neighbors:
                full_adj[src].append(tgt)

    type_name_map = {0: "T", 1: "M", 2: "A", 3: "O"}
    transition_counter = defaultdict(int)
    prereq_distances = []
    hybrid_reachable_count = 0

    _print_flush("--- Calculating connectivity (bounded BFS)... ---")
    for start_node, end_node in eval_samples:
        start_type = int(node_types[start_node].item())
        end_type = int(node_types[end_node].item())
        transition_counter[(start_type, end_type)] += 1

        # 先修图连通性 (简单 BFS 即可，因为先修图本身就是硬逻辑)
        queue = deque([(start_node, 0)])
        visited = {start_node}
        found_dist = None
        while queue:
            curr, dist = queue.popleft()
            if curr == end_node:
                found_dist = dist
                break
            for nxt in prereq_adj.get(curr, []):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, dist + 1))
        
        if found_dist is not None:
            prereq_distances.append(found_dist)

        # Hybrid/Soft 摘要只做节点级有界连通性统计，避免约束状态搜索造成内存爆炸。
        if env and _has_bounded_path(start_node, end_node, full_adj, max_depth=max_path_length):
            hybrid_reachable_count += 1

    _print_flush("--- Eval Sample Summary ---")
    _print_flush(f"  Total pairs: {len(eval_samples)}")
    _print_flush(
        f"  Graph reachable ratio (bounded, <= {max_path_length} hops): "
        f"{hybrid_reachable_count/len(eval_samples):.2%}"
    )

    if prereq_distances:
        _print_flush(
            f"  Prereq-only shortest distance: min={min(prereq_distances)}, "
            f"mean={np.mean(prereq_distances):.2f}, max={max(prereq_distances)}"
        )
        _print_flush(
            f"  Pure Prereq reachable ratio: {len(prereq_distances)/len(eval_samples):.2%}"
        )
    else:
        _print_flush("  Pure Prereq reachable ratio: 0.00%")

    sorted_transitions = sorted(
        transition_counter.items(), key=lambda x: x[1], reverse=True
    )
    _print_flush("  Top type transitions:")
    for (src_t, tgt_t), cnt in sorted_transitions[:8]:
        src_name = type_name_map.get(src_t, str(src_t))
        tgt_name = type_name_map.get(tgt_t, str(tgt_t))
        _print_flush(f"    {src_name}->{tgt_name}: {cnt}")


def generate_hierarchical_eval_samples(
    prereq_map: Dict[int, Set[int]],
    node_types: torch.Tensor,
    num_samples: int = 100,
    min_path_length: int = 3,
    max_path_length: int = 10,
    type_order: List[int] = None,
    rng: random.Random = None,
) -> List[Tuple[int, int]]:
    """
    基于层次（T→M→A→O）生成评估样本。

    策略：
    1. 起点优先选择基础理论（T）或方法（M）
    2. 终点优先选择应用（A）或工具（O）
    3. 确保起点和终点的类型符合认知顺序
    4. 确保路径长度在合理范围内

    Args:
        prereq_map: 先修关系映射 {目标节点: {先修节点集合}}
        node_types: 节点类型张量，0=Theory, 1=Method, 2=Application, 3=Tool
        num_samples: 需要生成的样本数量
        min_path_length: 最小路径长度（跳数）
        max_path_length: 最大路径长度（跳数）
        type_order: 类型顺序列表，默认为 [0, 1, 2, 3] (T->M->A->O)
        rng: 随机数生成器

    Returns:
        评估样本列表，每个样本是 (起点节点ID, 终点节点ID)
    """
    if rng is None:
        rng = random.Random(42)

    if type_order is None:
        type_order = [0, 1, 2, 3]  # Theory -> Method -> Application -> Tool

    # 构建邻接表用于 BFS
    adj = defaultdict(list)
    for tgt, srcs in prereq_map.items():
        for src in srcs:
            adj[src].append(tgt)

    # 定义类型层次约束
    type_hierarchies = [
        ([0, 1], [2, 3]),  # Theory/Method -> Application/Tool
        ([0], [1, 2, 3]),  # Theory -> Method/Application/Tool
        ([0, 1], [2]),  # Theory/Method -> Application
        ([0, 1, 2], [3]),  # Theory/Method/Application -> Tool
    ]

    candidates = []

    # 遍历所有可能的 (起点, 终点) 组合
    for start_node in range(len(node_types)):
        start_type = node_types[start_node].item()

        # 使用 BFS 计算从 start_node 到其他节点的最短路径
        queue = deque([(start_node, 0)])  # (node, distance)
        distances = {start_node: 0}
        visited = {start_node}

        while queue:
            curr, dist = queue.popleft()

            if dist > max_path_length:
                continue

            # 检查 curr 是否可以作为终点
            if dist >= min_path_length and curr != start_node:
                end_type = node_types[curr].item()

                # 检查类型层次是否合理
                valid_hierarchy = False
                for src_types, tgt_types in type_hierarchies:
                    if start_type in src_types and end_type in tgt_types:
                        valid_hierarchy = True
                        break

                if valid_hierarchy:
                    candidates.append((start_node, curr))

            # 扩展邻居
            for neighbor in adj.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    distances[neighbor] = dist + 1
                    queue.append((neighbor, dist + 1))

    # 如果候选样本不足，放宽约束
    if len(candidates) < num_samples:
        print(
            f"警告: 基于层次约束的候选样本不足 ({len(candidates)} < {num_samples})，放宽约束..."
        )
        # 放宽类型约束，只保证路径长度
        for start_node in range(len(node_types)):
            queue = deque([(start_node, 0)])
            distances = {start_node: 0}
            visited = {start_node}

            while queue:
                curr, dist = queue.popleft()

                if dist > max_path_length:
                    continue

                if dist >= min_path_length and curr != start_node:
                    candidates.append((start_node, curr))

                for neighbor in adj.get(curr, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        distances[neighbor] = dist + 1
                        queue.append((neighbor, dist + 1))

    # 去重并随机采样
    unique_candidates = list(set(candidates))

    if len(unique_candidates) < num_samples:
        print(
            f"警告: 即使放宽约束后，候选样本仍不足 ({len(unique_candidates)} < {num_samples})"
        )
        return unique_candidates

    return rng.sample(unique_candidates, num_samples)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(description="MOOCCubex Evaluation")
    # MOOCCubex 特定参数
    parser.add_argument("--data_dir", type=str, default="data/MOOCCubex")
    parser.add_argument("--field", type=str, default="心理学")
    parser.add_argument(
        "--hgt_emb_path", type=str, default="checkpoints/MOOCCubex/hgt_mooccubex.pt"
    )
    parser.add_argument(
        "--rl_model_path", type=str, default="checkpoints/MOOCCubex/rl_policy_last.pt"
    )

    # 评估参数
    parser.add_argument("--num_samples", type=int, default=100, help="评估样本数量")
    parser.add_argument("--max_path_length", type=int, default=25, help="最大路径长度")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument(
        "--use_hierarchical_sampling",
        action="store_true",
        help="是否使用基于层次（T→M→A→O）的评估样本生成（适用于MOOCCubex）",
    )
    parser.add_argument(
        "--min_path_length",
        type=int,
        default=3,
        help="评估样本的最小路径长度（仅在使用分层采样时有效）",
    )

    # 批量评估参数
    parser.add_argument(
        "--evaluate_all_checkpoints",
        action="store_true",
        help="是否评估所有检查点文件并生成训练曲线",
    )
    parser.add_argument(
        "--checkpoint_pattern",
        type=str,
        default="rl_policy_ep*.pt",
        help="检查点文件名匹配模式",
    )
    parser.add_argument(
        "--checkpoint_dir",
        type=str,
        default=None,
        help="检查点文件目录（如果未指定，将从 --rl_model_path 自动提取）",
    )
    parser.add_argument(
        "--skip_epochs",
        type=int,
        default=0,
        help="跳过前N个epoch的检查点（用于快速测试）",
    )
    parser.add_argument(
        "--evaluate_every",
        type=int,
        default=1,
        help="每隔N个epoch评估一次检查点（用于快速测试）",
    )

    # 评估模式
    parser.add_argument(
        "--evaluation_mode",
        type=str,
        default="practical",
        choices=["academic", "practical", "both"],
        help="评估模式: academic=学术指标(MRR/Hits@N), practical=实用指标(SR/PathLen), both=两者都计算。注意：对于 MOOCCubex 等路径规划任务，推荐使用 practical 模式，因为学术指标在密集图中容易失真",
    )
    parser.add_argument(
        "--eval_pairs_file",
        type=str,
        default=None,
        help="JSON file containing eval pairs to reuse (e.g. held-out samples from experiments)",
    )
    parser.add_argument(
        "--enable_filtered_ranking",
        action="store_true",
        help="是否启用 Filtered Ranking (仅学术模式有效)。注意：对于 MOOCCubex 等长路径导航任务，建议禁用此选项，因为 Filtered Ranking 会过滤掉合理的候选节点",
    )
    parser.add_argument(
        "--use_type_aware_ranking",
        action="store_true",
        help="是否使用类型感知的排名评估（推荐用于 MOOCCubex）。负样本将与真实目标属于同一类型，测试模型在同类候选中识别正确目标的能力",
    )
    parser.add_argument(
        "--num_neg_samples",
        type=int,
        default=99,
        help="每个正样本对应的负样本数量 (仅学术模式有效)",
    )

    # 兼容标准数据集的参数
    parser.add_argument(
        "--dataset_type",
        type=str,
        default="mooc",
        choices=["mooc", "standard"],
        help="数据集类型: mooc=MOOCCubex, standard=标准知识图谱",
    )
    parser.add_argument(
        "--dataset_name",
        type=str,
        default="MOOCCubex",
        help="数据集名称 (用于标准数据集)",
    )
    parser.add_argument("--save_plot", action="store_true", help="是否保存可视化图表")
    parser.add_argument(
        "--multi_seed_eval", action="store_true", help="是否进行多种子评估"
    )
    parser.add_argument(
        "--plot_filename_base",
        type=str,
        default="evaluation_summary",
        help="图表文件名前缀",
    )
    parser.add_argument("--gru_hidden_dim", type=int, default=64, help="GRU隐藏层维度")
    parser.add_argument("--use_cuda", action="store_true", help="是否使用 CUDA")

    parser.add_argument(
        "--constraint_mode",
        type=str,
        default="hybrid",
        choices=["strict", "hybrid", "soft"],
        help="RL 环境约束模式 (评估时建议与训练一致): strict=严格先修, hybrid=混合(软边可探索), soft=全放开(仅惩罚)",
    )
    args = parser.parse_args()

    # 如果未指定 checkpoint_dir，从 rl_model_path 自动提取
    if args.checkpoint_dir is None:
        args.checkpoint_dir = os.path.dirname(args.rl_model_path)
        print(f"--- Auto-detected checkpoint_dir: {args.checkpoint_dir} ---")

    set_seed(args.seed)
    device = torch.device("cuda" if args.use_cuda and torch.cuda.is_available() else "cpu")
    print(
        f"--- [Evaluation V3.0] Device: {device} | Mode: {args.evaluation_mode} | Seed: {args.seed} ---"
    )

    # 加载 HGT 嵌入
    if not os.path.exists(args.hgt_emb_path):
        raise FileNotFoundError(f"HGT file not found: {args.hgt_emb_path}")

    checkpoint = torch.load(args.hgt_emb_path, map_location=device, weights_only=False)
    hgt_embeddings = checkpoint["node_embeddings"].to(device)
    hgt_id_to_name = checkpoint["entity_map"]
    relation_map = checkpoint["relation_map"]
    raw_id_map = checkpoint.get("raw_id_map")
    prereq_map = checkpoint["prereq_map"]
    node_types = checkpoint["node_types"].to(device)

    # 加载知识图谱数据
    kg_json_path = os.path.join(args.data_dir, f"kg_data_{args.field}.json")
    if os.path.exists(kg_json_path):
        kg_data = load_custom_kg_from_json(kg_json_path)
    elif "MOOCCubex" in args.data_dir or args.dataset_type == "mooc":
        kg_data, _ = load_mooccubex_subgraph(args.data_dir, target_field=args.field)
    else:
        # 标准数据集或其他情况，如果不存在 field-specific 文件，抛出异常
        raise FileNotFoundError(f"未找到领域 [{args.field}] 的知识图谱数据: {kg_json_path}")

    # 处理图数据
    data, node_map, _, pagerank_values, _, _, _ = process_custom_kg(
        kg_data, 
        existing_node_map=hgt_id_to_name, 
        existing_relation_map=relation_map,
        existing_node_id_map={v: k for k, v in raw_id_map.items()} if raw_id_map else None
    )
    data = data.to(device)
    name_to_id = {name: i for i, name in node_map.items()}

    # 创建环境
    env = RLEnvironment(
        data=data,
        node_map=name_to_id,
        relation_map=relation_map,
        node_embeddings=hgt_embeddings,
        max_path_length=args.max_path_length,
        pagerank_values=pagerank_values,
        prerequisite_map=prereq_map,
        node_types=node_types,
        constraint_mode=args.constraint_mode
    )

    # 准备评估样本
    if args.eval_pairs_file and os.path.exists(args.eval_pairs_file):
        print(f"--- Loading held-out eval_pairs from {args.eval_pairs_file} ---")
        with open(args.eval_pairs_file, "r") as f:
            loaded_pairs = json.load(f)
            # JSON might serialize tuples to lists
            eval_samples = [(int(u), int(v)) for u, v in loaded_pairs]
        print(f"--- Loaded {len(eval_samples)} eval_pairs ---")
    elif args.use_hierarchical_sampling:
        print(f"--- Using Hierarchical Sampling (T→M→A→O) ---")
        eval_samples = generate_hierarchical_eval_samples(
            prereq_map=prereq_map,
            node_types=node_types,
            num_samples=args.num_samples,
            min_path_length=args.min_path_length,
            max_path_length=args.max_path_length,
            rng=random.Random(args.seed),
        )
        print(f"--- Generated {len(eval_samples)} hierarchical samples ---")
    else:
        print(f"--- Using Random Sampling (all prerequisite pairs) ---")
        test_pairs = []
        for tgt_idx, src_indices in prereq_map.items():
            for src_idx in src_indices:
                if src_idx < data.num_nodes and tgt_idx < data.num_nodes:
                    test_pairs.append((src_idx, tgt_idx))

        eval_samples = random.sample(test_pairs, min(len(test_pairs), args.num_samples))

    print(f"--- Starting Evaluation on {len(eval_samples)} samples ---")
    summarize_eval_samples(eval_samples, prereq_map, node_types, env=env, max_path_length=args.max_path_length)

    # 构建邻接表 (用于 Filtered Ranking)
    adj = defaultdict(list)
    for edge in kg_data["edges"]:
        h, r, t = edge["source"], edge["relation"], edge["target"]
        adj[h].append(t)

    # 构建所有已知三元组集合 (用于 Filtered Ranking)
    all_known_triplets: Optional[Set[Tuple[int, int, int]]] = None
    if args.enable_filtered_ranking:
        # 修正：将 source/target/relation 映射为数字 ID
        # 优先使用 raw_id_map 进行精确匹配，避免同名冲突
        if raw_id_map:
            old_id_to_new_id = {v: int(k) for k, v in raw_id_map.items()}
        else:
            old_id_to_new_id = {}
            for node in kg_data["nodes"]:
                # 回退方案：通过名称在 hgt_id_to_name 中查找
                for int_id, name in hgt_id_to_name.items():
                    if name == node["name"]:
                        old_id_to_new_id[node["id"]] = int(int_id)
                        break
        
        all_known_triplets = set()
        for edge in kg_data["edges"]:
            s_new = old_id_to_new_id.get(edge["source"])
            t_new = old_id_to_new_id.get(edge["target"])
            r_new = relation_map.get(edge["relation"])
            
            if s_new is not None and t_new is not None and r_new is not None:
                all_known_triplets.add((s_new, r_new, t_new))
        
        print(f"--- Filtered Ranking Enabled: {len(all_known_triplets)} known triplets mapped ---")

    # 加载 RL 模型
    policy_net = RLPolicyNet(
        hgt_embeddings.size(1), gru_hidden_dim=args.gru_hidden_dim
    ).to(device)

    # 创建报告目录（包含模式子目录，实现实验结果物理隔离）
    report_dir = f"reports/{args.dataset_name}/{args.seed}/{args.constraint_mode}/"
    os.makedirs(report_dir, exist_ok=True)

    # 批量评估所有检查点
    if args.evaluate_all_checkpoints:
        print(f"--- Batch Evaluation Mode: Evaluating all checkpoints ---")
        import glob
        import re

        # 收集所有检查点文件
        checkpoint_files = glob.glob(
            os.path.join(args.checkpoint_dir, args.checkpoint_pattern)
        )
        print(f"--- Found {len(checkpoint_files)} checkpoint files ---")

        # 从文件名中提取epoch编号并排序
        def extract_epoch(filename):
            match = re.search(r"ep(\d+)", filename)
            return int(match.group(1)) if match else -1

        checkpoint_files = sorted(checkpoint_files, key=extract_epoch)

        # 过滤检查点
        if args.skip_epochs > 0 or args.evaluate_every > 1:
            filtered_files = []
            for f in checkpoint_files:
                epoch = extract_epoch(f)
                if (
                    epoch >= args.skip_epochs
                    and (epoch - args.skip_epochs) % args.evaluate_every == 0
                ):
                    filtered_files.append(f)
            checkpoint_files = filtered_files
            print(
                f"--- After filtering: {len(checkpoint_files)} checkpoints to evaluate ---"
            )

        # 存储所有检查点的评估结果
        all_metrics_history = []

        # 依次评估每个检查点
        for i, checkpoint_path in enumerate(checkpoint_files):
            epoch = extract_epoch(checkpoint_path)
            print(
                f"\n--- [{i + 1}/{len(checkpoint_files)}] Evaluating Epoch {epoch}: {checkpoint_path} ---"
            )

            # 加载模型
            policy_net.load_state_dict(torch.load(checkpoint_path, map_location=device))

            # 评估
            if args.evaluation_mode == "practical":
                metrics = evaluate_navigation_metrics(
                    model=policy_net,
                    env=env,
                    eval_pairs=eval_samples,
                    node_embeddings=hgt_embeddings,
                    device=device,
                )
            elif args.evaluation_mode == "academic":
                metrics = evaluate_model_checkpoint(
                    model=policy_net,
                    env=env,
                    eval_pairs_positive=eval_samples,
                    adj=adj,
                    num_entities=data.num_nodes,
                    node_embeddings=hgt_embeddings,
                    device=device,
                    all_known_triplets=all_known_triplets,
                    num_candidate_neg_samples=args.num_neg_samples,
                    use_type_aware_ranking=args.use_type_aware_ranking,
                    node_types=node_types,
                    seed=args.seed,
                )
                metrics = {
                    k: v
                    for k, v in metrics.items()
                    if k in ["mrr", "hits@1", "hits@3", "hits@10"]
                }
            else:  # both
                metrics = evaluate_model_checkpoint(
                    model=policy_net,
                    env=env,
                    eval_pairs_positive=eval_samples,
                    adj=adj,
                    num_entities=data.num_nodes,
                    node_embeddings=hgt_embeddings,
                    device=device,
                    all_known_triplets=all_known_triplets,
                    num_candidate_neg_samples=args.num_neg_samples,
                    use_type_aware_ranking=args.use_type_aware_ranking,
                    node_types=node_types,
                    seed=args.seed,
                )

            # 添加epoch信息
            metrics["epoch"] = epoch
            all_metrics_history.append(metrics)

            # 打印当前结果
            if args.evaluation_mode != "academic":
                print(
                    f"  SR: {metrics.get('success_rate', 0):.2%} | "
                    f"AvgPath: {metrics.get('avg_path_length', 0):.2f} | "
                    f"PPC: {metrics.get('path_prereq_compliance', 0):.2%} | "
                    f"Rel-PPC: {metrics.get('target_relevant_ppc', 0):.2%} | "
                    f"TFC: {metrics.get('target_frontier_coverage', 0):.2%} | "
                    f"Hit: {metrics.get('frontier_hit_rate', 0):.2%} | "
                    f"Cond-TFC: {metrics.get('conditional_tfc', 0):.2%}"
                )
            if args.evaluation_mode != "practical":
                print(
                    f"  MRR: {metrics.get('mrr', 0):.4f} | Hits@1: {metrics.get('hits@1', 0):.2%}"
                )

        # 绘制训练曲线
        if args.save_plot and all_metrics_history:
            epochs = [m["epoch"] for m in all_metrics_history]

            # 保存完整的历史数据
            history_path = os.path.join(
                report_dir, f"{args.plot_filename_base}_training_history.json"
            )
            with open(history_path, "w") as f:
                json.dump(all_metrics_history, f, indent=2)
            print(f"--- Training history saved to: {history_path} ---")

            # 绘制学术指标曲线
            if args.evaluation_mode != "practical":
                academic_metrics = ["mrr", "hits@1", "hits@3", "hits@10"]
                for metric in academic_metrics:
                    if metric in all_metrics_history[0]:
                        values = [m[metric] for m in all_metrics_history]
                        plot_path = os.path.join(
                            report_dir,
                            f"{args.plot_filename_base}_{metric}_training_curve.png",
                        )
                        plot_metric_over_time(
                            metric_values=values,
                            metric_name=metric.upper().replace("@", "@"),
                            x_axis_values=epochs,
                            title=f"{metric.upper().replace('@', '@')} During Training",
                            xlabel="Training Epoch",
                            save_path=plot_path,
                        )
                        print(f"--- {metric} training curve saved to: {plot_path} ---")

            # 绘制导航指标曲线
            if args.evaluation_mode != "academic":
                nav_metrics = [
                    "success_rate",
                    "avg_path_length",
                    "path_prereq_compliance",
                    "target_frontier_coverage",
                ]
                for metric in nav_metrics:
                    if metric in all_metrics_history[0]:
                        values = [m[metric] for m in all_metrics_history]
                        plot_path = os.path.join(
                            report_dir,
                            f"{args.plot_filename_base}_{metric}_training_curve.png",
                        )
                        plot_metric_over_time(
                            metric_values=values,
                            metric_name=metric.replace("_", " ").title(),
                            x_axis_values=epochs,
                            title=f"{metric.replace('_', ' ').title()} During Training",
                            xlabel="Training Epoch",
                            save_path=plot_path,
                        )
                        print(f"--- {metric} training curve saved to: {plot_path} ---")

            # 绘制最终指标总结（使用最后一个检查点的结果）
            if all_metrics_history:
                final_metrics = {
                    k: v for k, v in all_metrics_history[-1].items() if k != "epoch"
                }
                if final_metrics:
                    summary_path = os.path.join(
                        report_dir, f"{args.plot_filename_base}_final_summary.png"
                    )
                    plot_metrics_summary(
                        metrics=final_metrics,
                        title=f"Final Evaluation Metrics (Epoch {all_metrics_history[-1]['epoch']})",
                        save_path=summary_path,
                    )
                    print(f"--- Final metrics summary saved to: {summary_path} ---")

        # 计算最终统计
        if all_metrics_history:
            # 获取最佳结果
            if args.evaluation_mode != "academic":
                best_sr_idx = max(
                    range(len(all_metrics_history)),
                    key=lambda i: all_metrics_history[i].get("success_rate", 0),
                )
                best_mrr_idx = max(
                    range(len(all_metrics_history)),
                    key=lambda i: all_metrics_history[i].get("mrr", 0),
                )
                print(f"\n--- Best Results ---")
                print(
                    f"  Best SR: {all_metrics_history[best_sr_idx].get('success_rate', 0):.2%} at Epoch {all_metrics_history[best_sr_idx]['epoch']}"
                )
                print(
                    f"  Best MRR: {all_metrics_history[best_mrr_idx].get('mrr', 0):.4f} at Epoch {all_metrics_history[best_mrr_idx]['epoch']}"
                )

            # 使用最后一个检查点的结果作为metrics
            metrics = all_metrics_history[-1]
        else:
            metrics = {}
    elif args.multi_seed_eval:
        # 多种子评估模式
        print(f"--- Multi-Seed Evaluation Mode ---")
        results = {}
        for seed in [42, 1984, 8888]:
            model_path = args.rl_model_path.replace("{seed}", str(seed))
            if os.path.exists(model_path):
                policy_net.load_state_dict(torch.load(model_path, map_location=device))
                print(f"--- Loaded RL Model: {model_path} ---")

                # 评估
                metrics = evaluate_model_checkpoint(
                    model=policy_net,
                    env=env,
                    eval_pairs_positive=eval_samples,
                    adj=adj,
                    num_entities=data.num_nodes,
                    node_embeddings=hgt_embeddings,
                    device=device,
                    all_known_triplets=all_known_triplets
                    if args.enable_filtered_ranking
                    else None,
                    num_candidate_neg_samples=args.num_neg_samples,
                    use_type_aware_ranking=args.use_type_aware_ranking,
                    node_types=node_types,
                    seed=seed,
                )
                results[f"seed_{seed}"] = metrics
            else:
                print(f"--- Warning: Model not found: {model_path} ---")

        # 聚合结果
        if results:
            aggregated = {}
            for metric_name in results[list(results.keys())[0]].keys():
                values = [r[metric_name] for r in results.values()]
                aggregated[f"{metric_name}_mean"] = np.mean(values)
                aggregated[f"{metric_name}_std"] = np.std(values)
            metrics = aggregated
        else:
            metrics = {}
    else:
        # 单模型评估
        if os.path.exists(args.rl_model_path):
            policy_net.load_state_dict(
                torch.load(args.rl_model_path, map_location=device)
            )
            print(f"--- Loaded RL Model: {args.rl_model_path} ---")
        else:
            print(f"--- Warning: RL model not found at {args.rl_model_path} ---")

        # 根据评估模式选择评估函数
        if args.evaluation_mode == "practical":
            # 只计算实用指标 (快速)
            metrics = evaluate_navigation_metrics(
                model=policy_net,
                env=env,
                eval_pairs=eval_samples,
                node_embeddings=hgt_embeddings,
                device=device,
            )
        elif args.evaluation_mode == "academic":
            # 只计算学术指标 (较慢)
            metrics = evaluate_model_checkpoint(
                model=policy_net,
                env=env,
                eval_pairs_positive=eval_samples,
                adj=adj,
                num_entities=data.num_nodes,
                node_embeddings=hgt_embeddings,
                device=device,
                all_known_triplets=all_known_triplets,
                num_candidate_neg_samples=args.num_neg_samples,
                use_type_aware_ranking=args.use_type_aware_ranking,
                node_types=node_types,
                seed=args.seed,
            )
            # 移除导航指标 (学术模式只关注排名指标)
            metrics = {
                k: v
                for k, v in metrics.items()
                if k in ["mrr", "hits@1", "hits@3", "hits@10"]
            }
        else:  # both
            # 计算所有指标
            metrics = evaluate_model_checkpoint(
                model=policy_net,
                env=env,
                eval_pairs_positive=eval_samples,
                adj=adj,
                num_entities=data.num_nodes,
                node_embeddings=hgt_embeddings,
                device=device,
                all_known_triplets=all_known_triplets,
                num_candidate_neg_samples=args.num_neg_samples,
                use_type_aware_ranking=args.use_type_aware_ranking,
                node_types=node_types,
                seed=args.seed,
            )

    # 打印结果
    print("\n" + "=" * 60)
    print(f"Evaluation Results (V3.0 - Corrected Metrics)")
    print("=" * 60)

    # 分组显示指标
    if "success_rate" in metrics:
        print(f"\n🎯 Navigation Metrics (Practical):")
        print(f"  Success Rate:              {metrics['success_rate']:.2%}")
        print(f"  Avg Path Length:           {metrics['avg_path_length']:.2f}")
        if "path_prereq_compliance" in metrics:
            print(f"  Path Prereq Compliance (PPC): {metrics['path_prereq_compliance']:.2%}")
        if "target_relevant_ppc" in metrics:
            print(f"  Target-Relevant PPC:          {metrics['target_relevant_ppc']:.2%}")
        if "target_frontier_coverage" in metrics:
            print(f"  Target Frontier Coverage (TFC): {metrics['target_frontier_coverage']:.2%}")
        if "frontier_hit_rate" in metrics:
            print(f"  Frontier Hit Rate:            {metrics['frontier_hit_rate']:.2%}")
        if "conditional_tfc" in metrics:
            print(f"  Conditional TFC:              {metrics['conditional_tfc']:.2%}")

    if "mrr" in metrics:
        print(f"\n📊 Ranking Metrics (Academic):")
        print(f"  MRR:               {metrics['mrr']:.4f}")
        if "hits@1" in metrics:
            print(f"  Hits@1:            {metrics['hits@1']:.2%}")
        if "hits@3" in metrics:
            print(f"  Hits@3:            {metrics['hits@3']:.2%}")
        if "hits@10" in metrics:
            print(f"  Hits@10:           {metrics['hits@10']:.2%}")

    print("=" * 60)

    # 保存结果
    if args.save_plot:
        # 保存 JSON 结果
        json_path = os.path.join(report_dir, f"{args.plot_filename_base}_metrics.json")
        with open(json_path, "w") as f:
            json.dump(metrics, f, indent=2)
        print(f"--- Metrics saved to: {json_path} ---")

        # 可视化
        if args.evaluation_mode != "practical":
            # 学术指标可视化
            academic_metrics = {
                k: v
                for k, v in metrics.items()
                if any(x in k for x in ["mrr", "hits@"])
            }
            if academic_metrics:
                plt.figure(figsize=(10, 6))
                # 过滤掉标准差指标
                display_metrics = {
                    k: v for k, v in academic_metrics.items() if "_std" not in k
                }
                bars = plt.bar(
                    display_metrics.keys(),
                    display_metrics.values(),
                    color="skyblue",
                    alpha=0.7,
                )
                plt.title(f"Academic Metrics - {args.dataset_name}")
                plt.ylim(0, 1.1)
                plt.xticks(rotation=45)
                plt.tight_layout()
                plot_path = os.path.join(
                    report_dir, f"{args.plot_filename_base}_academic.png"
                )
                plt.savefig(plot_path, dpi=150)
                plt.close()
                print(f"--- Academic plot saved to: {plot_path} ---")

        if args.evaluation_mode != "academic":
            # 导航指标可视化
            nav_metrics = {
                k: v
                for k, v in metrics.items()
                if k in [
                    "success_rate",
                    "avg_path_length",
                    "path_prereq_compliance",
                    "target_frontier_coverage",
                ]
            }
            if nav_metrics:
                plt.figure(figsize=(10, 6))
                bars = plt.bar(
                    nav_metrics.keys(),
                    nav_metrics.values(),
                    color="lightcoral",
                    alpha=0.7,
                )
                plt.title(f"Navigation Metrics - {args.dataset_name}")
                if any("rate" in k or "ratio" in k for k in nav_metrics):
                    plt.ylim(0, 1.1)
                plt.tight_layout()
                plot_path = os.path.join(
                    report_dir, f"{args.plot_filename_base}_navigation.png"
                )
                plt.savefig(plot_path, dpi=150)
                plt.close()
                print(f"--- Navigation plot saved to: {plot_path} ---")

    print(f"--- Evaluation Complete ---")


if __name__ == "__main__":
    main()
