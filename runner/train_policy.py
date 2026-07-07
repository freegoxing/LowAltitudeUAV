"""
MOOCCubex 强化学习训练脚本 (学术增强 + 严格对齐 V2.7)
"""

import argparse
import json
import logging
import os
import random
import threading
from collections import defaultdict

import numpy as np
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP

from hgt_rl_planner.data_loader import load_mooccubex_subgraph
from hgt_rl_planner.models import RLPolicyNet
from hgt_rl_planner.environment import RLEnvironment
from hgt_rl_planner.trainer import RLTrainer
from hgt_rl_planner.utils.data_processing import process_custom_kg
from hgt_rl_planner.utils.seeding import set_seed

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def is_distributed() -> bool:
    return dist.is_available() and dist.is_initialized()


def get_rank() -> int:
    return dist.get_rank() if is_distributed() else 0


def get_world_size() -> int:
    return dist.get_world_size() if is_distributed() else 1


def is_main_process() -> bool:
    return get_rank() == 0


def unwrap_model(model):
    return model.module if isinstance(model, DDP) else model


def reduce_mean(value: float, device: torch.device) -> float:
    if not is_distributed():
        return float(value)
    tensor = torch.tensor(float(value), device=device)
    dist.all_reduce(tensor, op=dist.ReduceOp.SUM)
    tensor /= get_world_size()
    return float(tensor.item())


def setup_distributed(args) -> tuple[torch.device, int]:
    if not args.distributed:
        device = torch.device("cuda" if args.use_cuda and torch.cuda.is_available() else "cpu")
        return device, 0

    if not args.use_cuda or not torch.cuda.is_available():
        raise RuntimeError("--distributed 需要配合可用的 CUDA 设备")

    if "LOCAL_RANK" not in os.environ:
        raise RuntimeError("未检测到 LOCAL_RANK，请使用 torchrun 启动分布式训练")

    local_rank = int(os.environ["LOCAL_RANK"])
    torch.cuda.set_device(local_rank)
    dist.init_process_group(backend="nccl")
    device = torch.device("cuda", local_rank)
    return device, local_rank


def cleanup_distributed():
    if is_distributed():
        dist.destroy_process_group()


def async_save_checkpoint(model_state_dict, checkpoint_path: str, history: dict = None, metrics_path: str = ""):
    """后台异步保存 checkpoint，可选保存训练历史"""
    try:
        # 1. 保存模型 checkpoint (核心任务)
        os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
        torch.save(model_state_dict, checkpoint_path)
        logging.info(f">>> [Async] Model checkpoint saved: {checkpoint_path}")

        # 2. 只有当路径非空且有历史数据时才尝试保存指标
        if metrics_path and history:
            metrics_dir = os.path.dirname(metrics_path)
            if metrics_dir: # 避免 os.makedirs("")
                os.makedirs(metrics_dir, exist_ok=True)
            with open(metrics_path, "w") as f:
                json.dump(history, f, indent=2)
            logging.info(f">>> [Async] History metrics saved: {metrics_path}")
            
    except Exception as e:
        logging.error(f">>> [Async] Failed to save during background task: {e}")


def main():
    parser = argparse.ArgumentParser(description="KG-GNN RL Path Planner")
    parser.add_argument("--data_dir", type=str, default="data/MOOCCubex")
    parser.add_argument("--field", type=str, default="心理学")
    parser.add_argument("--dataset_type", type=str, default="mooc", choices=["mooc", "standard"])
    parser.add_argument("--dataset_name", type=str, default="MOOCCubex")
    parser.add_argument(
        "--hgt_emb_path", type=str, default="checkpoints/MOOCCubex/hgt_mooccubex.pt"
    )
    parser.add_argument(
        "--rl_save_path", type=str, default="checkpoints/MOOCCubex/rl_policy_last.pt"
    )
    parser.add_argument("--max_path_length", type=int, default=15)
    parser.add_argument("--epochs", type=int, default=2000)
    parser.add_argument(
        "--batch_size", type=int, default=256, help="针对 5090 建议 256-512"
    )
    parser.add_argument("--lr", type=float, default=0.0005)
    parser.add_argument("--gru_hidden_dim", type=int, default=64)
    parser.add_argument("--reward_lambda", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--metrics_path", type=str, default="reports/MOOCCubex/train_metrics.json"
    )
    parser.add_argument(
        "--use_amp", action="store_true", help="使用混合精度训练（AMP）"
    )
    parser.add_argument(
        "--save_every", type=int, default=5000, help="每隔多少轮次保存checkpoint和评估"
    )
    parser.add_argument(
        "--eval_num_samples", type=int, default=50, help="评估时使用的样本数量"
    )
    parser.add_argument("--use_cuda", action="store_true")
    parser.add_argument(
        "--distributed",
        action="store_true",
        help="启用基于 torch.distributed 的多 GPU DDP 训练",
    )

    parser.add_argument(
        "--constraint_mode",
        type=str,
        default="hybrid",
        choices=["strict", "hybrid", "soft"],
        help="RL 环境约束模式: strict=严格先修, hybrid=混合(软边可探索), soft=全放开(仅惩罚)",
    )
    args = parser.parse_args()

    # 处理标准数据集路径
    if args.dataset_type == "standard" and args.dataset_name:
        args.data_dir = f"data/{args.dataset_name}"
        args.hgt_emb_path = f"checkpoints/{args.dataset_name}/hgt_{args.dataset_name}.pt"
        args.rl_save_path = f"checkpoints/{args.dataset_name}/rl_policy_last.pt"
        args.metrics_path = f"reports/{args.dataset_name}/train_metrics.json"
        os.makedirs(os.path.dirname(args.rl_save_path), exist_ok=True)
        os.makedirs(os.path.dirname(args.metrics_path), exist_ok=True)


    device, local_rank = setup_distributed(args)
    rank = get_rank()
    world_size = get_world_size()
    
    # --- 种子逻辑对齐 V2 ---
    # 1. 首先设置全局统一种子，确保各卡生成的 curriculum_pairs 和 eval_pairs 完全一致
    set_seed(args.seed)
    
    print(
        f"--- [RL Train] Device: {device} | Field: {args.field} | AMP: {args.use_amp} | "
        f"Distributed: {args.distributed} | Rank: {rank}/{world_size} | Global Seed: {args.seed} ---"
    )

    if not os.path.exists(args.hgt_emb_path):
        raise FileNotFoundError(f"HGT Checkpoint not found at {args.hgt_emb_path}")

    checkpoint = torch.load(args.hgt_emb_path, map_location=device, weights_only=False)
    hgt_embeddings = checkpoint["node_embeddings"].to(device)
    hgt_id_to_name = checkpoint["entity_map"]
    relation_map = checkpoint["relation_map"]
    raw_id_map = checkpoint.get("raw_id_map")
    prereq_map = checkpoint["prereq_map"]
    node_types = checkpoint["node_types"].to(device)
    print(f"--- Loaded HGT Embeddings: {hgt_embeddings.shape} ---")

    from hgt_rl_planner.data_loader import (
        load_custom_kg_from_json,
        load_mooccubex_subgraph,
    )

    # 使用字段特定的 kg_data_{field}.json，确保领域隔离
    kg_json_path = os.path.join(args.data_dir, f"kg_data_{args.field}.json")
    if os.path.exists(kg_json_path):
        kg_data = load_custom_kg_from_json(kg_json_path)
    elif "MOOCCubex" in args.data_dir:
        kg_data, _ = load_mooccubex_subgraph(args.data_dir, target_field=args.field)
    else:
        raise FileNotFoundError(f"未找到领域 [{args.field}] 的知识图谱数据: {kg_json_path}")

    data, node_map, _, pagerank_values, _, _, _ = process_custom_kg(
        kg_data, 
        existing_node_map=hgt_id_to_name, 
        existing_relation_map=relation_map,
        existing_node_id_map={v: k for k, v in raw_id_map.items()} if raw_id_map else None
    )
    data = data.to(device)
    name_to_id = {name: i for i, name in node_map.items()}
    print(f"--- Graph loaded, Nodes: {data.num_nodes} ---")

    env = RLEnvironment(
        data=data,
        node_map=name_to_id,
        relation_map=relation_map,
        node_embeddings=hgt_embeddings,
        max_path_length=args.max_path_length,
        pagerank_values=pagerank_values,
        prerequisite_map=prereq_map,
        node_types=node_types,
        reward_lambda=args.reward_lambda,
        constraint_mode=args.constraint_mode,
    )

    policy_net = RLPolicyNet(hgt_embeddings.size(1), gru_hidden_dim=args.gru_hidden_dim).to(device)
    if args.distributed:
        policy_net = DDP(policy_net, device_ids=[local_rank], output_device=local_rank)
    trainer = RLTrainer(env, policy_net, hgt_embeddings, device, learning_rate=args.lr)

    # 初始化混合精度训练（AMP）
    if args.use_amp and device.type == "cuda":
        scaler = torch.amp.GradScaler("cuda")
        print(f"--- [RL Train] AMP Enabled: Using Tensor Core for 2-3x Speedup ---")
    else:
        scaler = None

    # 5. 构建训练样本对 (由于上面 set_seed(args.seed)，此处全卡一致)
    target_pairs = []
    # A. 基础先修对
    for tgt_idx, src_indices in prereq_map.items():
        for src_idx in src_indices:
            if src_idx < data.num_nodes and tgt_idx < data.num_nodes:
                target_pairs.append((src_idx, tgt_idx))

    # B. 长程认知路径
    print(f"--- Generating long-range curriculum pairs (Hybrid mode)... ---")
    from hgt_rl_planner.evaluation_lib import sample_curriculum_pairs_by_constrained_walk
    curriculum_pairs = sample_curriculum_pairs_by_constrained_walk(env, num_samples=min(2000, data.num_nodes * 2))
    target_pairs.extend(curriculum_pairs)
    
    print(f"--- Total Training Pairs: {len(target_pairs)} (Base: {len(target_pairs)-len(curriculum_pairs)} + Long: {len(curriculum_pairs)}) ---")

    if not target_pairs:
        concept_indices = list(range(data.num_nodes))
        for _ in range(500):
            target_pairs.append(random.sample(concept_indices, 2))

    eval_pairs = random.sample(target_pairs, min(len(target_pairs), args.eval_num_samples))


    set_seed(args.seed)

    global_batch_size = args.batch_size * world_size
    # 语义回归：epochs 代表总样本数 (Total Episodes)，num_batches 代表总优化步数
    num_batches = max(1, args.epochs // global_batch_size)

    print(
        f"--- Starting RL Training ---"
        f"\n  | Total Expected Episodes: {args.epochs}"
        f"\n  | Per-GPU Batch: {args.batch_size}"
        f"\n  | Global Batch Size: {global_batch_size}"
        f"\n  | Total Update Steps (Batches): {num_batches}"
        f"\n  | Rank: {rank} Seed: {args.seed + rank}"
    )


    history = defaultdict(list)
    total_rewards = []
    
    try:
        for b in range(1, num_batches + 1):
            batch_pairs = [random.choice(target_pairs) for _ in range(args.batch_size)]

            with torch.autocast(device_type="cuda" if "cuda" in device.type else "cpu", enabled=(scaler is not None)):
                avg_reward, sr, loss = trainer.train_batch(batch_pairs)

            trainer.optimizer.zero_grad()
            if loss is not None and isinstance(loss, torch.Tensor):
                if scaler is not None:
                    scaler.scale(loss).backward()
                    scaler.unscale_(trainer.optimizer)
                    torch.nn.utils.clip_grad_norm_(policy_net.parameters(), 1.0)
                    scaler.step(trainer.optimizer)
                    scaler.update()
                else:
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(policy_net.parameters(), 1.0)
                    trainer.optimizer.step()

            avg_reward = reduce_mean(avg_reward, device)
            sr = reduce_mean(sr, device)
            total_rewards.append(avg_reward)
            ep_count = b * global_batch_size

            if is_main_process() and b % 20 == 0:
                logging.info(
                    f"Batch {b}/{num_batches} | Ep {ep_count} | Reward: {avg_reward:.2f} | SR: {sr:.2%}"
                )

            if ep_count % args.save_every < global_batch_size and ep_count >= args.save_every:
                if is_distributed():
                    dist.barrier()

                if is_main_process():
                    base_model = unwrap_model(policy_net)
                    base_model.eval()
                    checkpoint_dir = os.path.dirname(args.rl_save_path)
                    checkpoint_name = os.path.basename(args.rl_save_path).replace(
                        "_last.pt", f"_ep{ep_count}.pt"
                    )
                    checkpoint_path = os.path.join(checkpoint_dir, checkpoint_name)

                    checkpoint_copy = {k: v.cpu().clone() for k, v in base_model.state_dict().items()}

                    save_thread = threading.Thread(
                        target=async_save_checkpoint,
                        args=(checkpoint_copy, checkpoint_path, {}, "")
                    )
                    save_thread.start()

                    from hgt_rl_planner.evaluation_lib import evaluate_navigation_metrics
                    eval_metrics = evaluate_navigation_metrics(
                        model=base_model, env=env, eval_pairs=eval_pairs,
                        node_embeddings=hgt_embeddings, device=device,
                        metric_prerequisite_map=prereq_map,
                    )

                    history["episode"].append(ep_count)
                    history["avg_reward"].append(float(np.mean(total_rewards[-20:])))
                    history["success_rate"].append(eval_metrics["success_rate"])
                    history["avg_path_length"].append(eval_metrics["avg_path_length"])
                    history["path_prereq_compliance"].append(
                        eval_metrics.get("path_prereq_compliance", 0.0)
                    )
                    history["target_relevant_ppc"].append(
                        eval_metrics.get("target_relevant_ppc", 0.0)
                    )
                    history["target_frontier_coverage"].append(
                        eval_metrics.get("target_frontier_coverage", 0.0)
                    )
                    history["frontier_hit_rate"].append(
                        eval_metrics.get("frontier_hit_rate", 0.0)
                    )
                    history["conditional_tfc"].append(
                        eval_metrics.get("conditional_tfc", 0.0)
                    )

                    os.makedirs(os.path.dirname(args.metrics_path), exist_ok=True)
                    with open(args.metrics_path, "w") as f:
                        json.dump(history, f, indent=2)

                    logging.info(
                        f">>> Eval @ {ep_count} | SR: {eval_metrics['success_rate']:.2%} | "
                        f"Avg Path: {eval_metrics['avg_path_length']:.2f} | "
                        f"PPC: {eval_metrics.get('path_prereq_compliance', 0.0):.2%} | "
                        f"Rel-PPC: {eval_metrics.get('target_relevant_ppc', 0.0):.2%} | "
                        f"TFC: {eval_metrics.get('target_frontier_coverage', 0.0):.2%} | "
                        f"Hit: {eval_metrics.get('frontier_hit_rate', 0.0):.2%} | "
                        f"Cond-TFC: {eval_metrics.get('conditional_tfc', 0.0):.2%}"
                    )
                    base_model.train()

                if is_distributed():
                    dist.barrier()

        if is_distributed():
            dist.barrier()

        if is_main_process():
            base_model = unwrap_model(policy_net)
            os.makedirs(os.path.dirname(args.rl_save_path), exist_ok=True)
            torch.save(base_model.state_dict(), args.rl_save_path)
            logging.info(f">>> Final model saved: {args.rl_save_path}")

            os.makedirs(os.path.dirname(args.metrics_path), exist_ok=True)
            with open(args.metrics_path, "w") as f:
                json.dump(history, f, indent=2)
            logging.info(f">>> Final training history saved: {args.metrics_path}")

            print(f"--- Training Finished. Model saved to: {args.rl_save_path} ---")
    finally:
        cleanup_distributed()


if __name__ == "__main__":
    main()
