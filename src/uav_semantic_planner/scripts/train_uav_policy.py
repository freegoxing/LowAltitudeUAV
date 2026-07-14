"""
UAV 语义通信网络强化学习训练脚本
(动态权重版 - 模拟 Agent 2 的多策略切换)
"""

import argparse
import logging
import os
import random
import sys

# 自动处理路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

from uav_semantic_planner.envs.environment import UAVRLEnvironment  # noqa: E402
from uav_semantic_planner.models.models import (  # noqa: E402
    RLPolicyNet,
    UAVHGTEncoder,
)
from uav_semantic_planner.trainer.trainer import RLTrainer  # noqa: E402
from uav_semantic_planner.utils.seeding import set_seed  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def main():
    parser = argparse.ArgumentParser(description="UAV Semantic RL Routing Planner")
    parser.add_argument(
        "--graph_pt", type=str, default="checkpoints/UAV_Demo/uav_hetero_graph.pt"
    )
    parser.add_argument("--save_dir", type=str, default="checkpoints/UAV_Demo/")

    parser.add_argument("--embedding_dim", type=int, default=128)
    parser.add_argument("--gru_hidden_dim", type=int, default=64)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=1000)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--hgt_pretrain_epochs", type=int, default=300)
    parser.add_argument("--hgt_lr", type=float, default=0.001)
    parser.add_argument(
        "--encoder_pt",
        type=str,
        default=None,
        help="HGT 热启动权重：支持纯 encoder state_dict 或联合训练 checkpoint",
    )
    parser.add_argument("--max_path_length", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)

    # 模拟 Agent 2 的奖励权重 [w_snr_gain, w_bottleneck, w_stability]
    parser.add_argument("--w_snr", type=float, default=1.0)
    parser.add_argument("--w_btnk", type=float, default=1.5)
    parser.add_argument("--w_stab", type=float, default=0.5)

    args = parser.parse_args()

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"--- [RL Train] Device: {device} | Seed: {args.seed} ---")

    # 1. 加载图谱预处理缓存
    if not os.path.exists(args.graph_pt):
        raise FileNotFoundError(f"未找到预处理图数据: {args.graph_pt}")

    checkpoint = torch.load(args.graph_pt, map_location=device, weights_only=False)

    x_dict_ids = checkpoint["x_dict_ids"]
    edge_index_dict = checkpoint["edge_index_dict"]
    metadata = checkpoint["metadata"]
    weak_link_index = checkpoint["weak_link_index"]
    num_nodes_dict = checkpoint["num_nodes_dict"]

    node_map = checkpoint["node_map"]
    relation_map = checkpoint["relation_map"]
    pagerank_values = checkpoint["pagerank_values"]
    node_types = checkpoint["node_types"].to(device)
    snr_map = checkpoint["snr_map"]
    weak_link_set = checkpoint["weak_link_set"]

    # 为了方便索引，这里构建一个临时的 Data 对象给环境用
    # (在真实场景中，这里的 edge_index 可能需要根据 edge_index_dict 重新拼合)
    # 此处简化：由于我们没有存原生的 data 对象，环境实际上主要用 adjacency_list
    from torch_geometric.data import Data

    # 拼接原始的 edge_index
    src_list, dst_list, type_list = [], [], []
    for (ut, rel_name, vt), e_idx in edge_index_dict.items():
        # HGT 的 edge_index 是每个节点类型内的局部索引，环境需要全局索引。
        src_list.append(x_dict_ids[ut][e_idx[0]])
        dst_list.append(x_dict_ids[vt][e_idx[1]])
        type_list.append(torch.full((e_idx.size(1),), relation_map[rel_name]))

    if src_list:
        srcs = torch.cat(src_list)
        dsts = torch.cat(dst_list)
        full_edge_index = torch.stack([srcs, dsts], dim=0)
        full_edge_type = torch.cat(type_list)
    else:
        full_edge_index = torch.empty((2, 0), dtype=torch.long)
        full_edge_type = torch.empty(0, dtype=torch.long)

    total_nodes = sum(num_nodes_dict.values())
    data = Data(
        edge_index=full_edge_index.to(device),
        edge_type=full_edge_type.to(device),
        num_nodes=total_nodes,
    )

    # 2. 初始化编码器并计算特征 (在这里我们模拟端到端训练，先通过 Encoder 拿到 Emb)
    print("--- 初始化 UAVHGTEncoder ---")
    encoder = UAVHGTEncoder(
        num_nodes_dict=num_nodes_dict,
        embedding_dim=args.embedding_dim,
        hidden_channels=args.embedding_dim,
        out_channels=args.embedding_dim,
        metadata=metadata,
    ).to(device)
    if args.encoder_pt is not None:
        if not os.path.exists(args.encoder_pt):
            raise FileNotFoundError(f"未找到 encoder 权重: {args.encoder_pt}")
        encoder_checkpoint = torch.load(
            args.encoder_pt, map_location=device, weights_only=True
        )
        if (
            isinstance(encoder_checkpoint, dict)
            and "encoder_state_dict" in encoder_checkpoint
        ):
            saved_dim = encoder_checkpoint.get("embedding_dim")
            if saved_dim is not None and saved_dim != args.embedding_dim:
                raise ValueError(
                    f"encoder embedding_dim={saved_dim} 与当前 "
                    f"--embedding_dim={args.embedding_dim} 不一致"
                )
            encoder_state = encoder_checkpoint["encoder_state_dict"]
        else:
            encoder_state = encoder_checkpoint
        try:
            encoder.load_state_dict(encoder_state)
        except RuntimeError as exc:
            raise ValueError("encoder 权重与当前图 metadata/模型维度不兼容") from exc
        print(f"--- 已热启动 HGT Encoder: {args.encoder_pt} ---")

    # 获取节点的初始特征表达
    for k in x_dict_ids:
        x_dict_ids[k] = x_dict_ids[k].to(device)
    for k in edge_index_dict:
        edge_index_dict[k] = edge_index_dict[k].to(device)
    if weak_link_index is not None:
        weak_link_index = weak_link_index.to(device)

    # 用最短图距离作为自监督信号，避免将随机 HGT 嵌入冻结给 RL。
    # 目标相似度随距离衰减，不可达节点的目标为 0。
    distance = torch.full((total_nodes, total_nodes), float("inf"), device=device)
    distance.fill_diagonal_(0)
    if full_edge_index.numel() > 0:
        distance[full_edge_index[0], full_edge_index[1]] = 1
    for k in range(total_nodes):
        distance = torch.minimum(distance, distance[:, k : k + 1] + distance[k : k + 1])
    similarity_target = torch.where(
        torch.isfinite(distance), torch.exp(-distance / 2.0), torch.zeros_like(distance)
    )

    if args.hgt_pretrain_epochs > 0:
        print(f"--- HGT 图距离自监督预训练: {args.hgt_pretrain_epochs} epochs ---")
        encoder_optimizer = torch.optim.AdamW(encoder.parameters(), lr=args.hgt_lr)
        encoder.train()
        for epoch in range(1, args.hgt_pretrain_epochs + 1):
            h_dict = encoder(x_dict_ids, edge_index_dict, weak_link_index)
            embeddings = torch.zeros(total_nodes, args.embedding_dim, device=device)
            for nt, h_tensor in h_dict.items():
                embeddings[x_dict_ids[nt]] = h_tensor
            normalized = F.normalize(embeddings, dim=-1)
            predicted = normalized @ normalized.T
            loss = F.mse_loss(predicted, similarity_target)
            encoder_optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(encoder.parameters(), 1.0)
            encoder_optimizer.step()
            if epoch == 1 or epoch % 50 == 0 or epoch == args.hgt_pretrain_epochs:
                logging.info(
                    "HGT pretrain %d/%d | Loss: %.6f",
                    epoch,
                    args.hgt_pretrain_epochs,
                    loss.item(),
                )

    encoder.eval()
    with torch.no_grad():
        h_dict = encoder(x_dict_ids, edge_index_dict, weak_link_index)

        # 将分类型的 embedding 拼合成一个连续的 tensor，与 node_types 对应的全局 ID 匹配
        node_embeddings = torch.zeros(total_nodes, args.embedding_dim, device=device)
        # 根据 global_to_local 逻辑还原
        # 因为 x_dict_ids 里存的是全局 ID，直接赋值即可
        for nt, h_tensor in h_dict.items():
            global_indices = x_dict_ids[nt]
            node_embeddings[global_indices] = h_tensor

    # 3. 初始化 RL 环境和策略网络
    agent2_weights = [args.w_snr, args.w_btnk, args.w_stab]
    print(
        f"--- 任务模式权重: SNR增益={args.w_snr}, 瓶颈容忍={args.w_btnk}, 稳定性={args.w_stab} ---"
    )

    env = UAVRLEnvironment(
        data=data,
        node_map=node_map,
        relation_map=relation_map,
        node_embeddings=node_embeddings,
        max_path_length=args.max_path_length,
        pagerank_values=pagerank_values,
        snr_map=snr_map,
        weak_link_set=weak_link_set,
        node_types=node_types,
        reward_weights=agent2_weights,
    )

    policy_net = RLPolicyNet(
        embedding_dim=args.embedding_dim, gru_hidden_dim=args.gru_hidden_dim
    ).to(device)

    trainer = RLTrainer(
        env=env,
        policy_net=policy_net,
        node_embeddings=node_embeddings,
        device=device,
        learning_rate=args.lr,
    )

    # 4. 准备训练集 (采样可达的端到端通信对)
    from uav_semantic_planner.utils.evaluation_lib import (
        evaluate_navigation_metrics,
        sample_uav_communication_pairs,
    )

    print("--- 正在采样通信对 ---")
    target_pairs = sample_uav_communication_pairs(env, num_samples=2000)
    eval_pairs = random.sample(target_pairs, min(len(target_pairs), 100))
    eval_pair_set = set(eval_pairs)
    target_pairs = [pair for pair in target_pairs if pair not in eval_pair_set]
    print(f"--- 采得训练对: {len(target_pairs)}, 评估对: {len(eval_pairs)} ---")

    if not target_pairs:
        raise ValueError(
            "未能采样到任何可达通信对，请检查图是否连通或 SNR 阈值是否过高"
        )

    # 5. 训练循环
    num_batches = max(1, args.epochs // args.batch_size)
    print("--- 开始训练 ---")
    for b in range(1, num_batches + 1):
        batch_pairs = [random.choice(target_pairs) for _ in range(args.batch_size)]

        avg_reward, sr, loss = trainer.train_batch(batch_pairs)

        trainer.optimizer.zero_grad()
        if loss is not None:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy_net.parameters(), 1.0)
            trainer.optimizer.step()

        if b % 10 == 0:
            logging.info(
                f"Batch {b}/{num_batches} | Reward: {avg_reward:.2f} | SR: {sr:.2%} | Loss: {loss.detach().item():.4f}"
            )

        if b % 50 == 0 or b == num_batches:
            eval_metrics = evaluate_navigation_metrics(
                model=policy_net,
                env=env,
                eval_pairs=eval_pairs,
                node_embeddings=node_embeddings,
                device=device,
            )
            logging.info(
                f">>> Eval @ Batch {b} | SR: {eval_metrics['success_rate']:.2%} | "
                f"Avg Path: {eval_metrics['avg_path_length']:.2f} | "
                f"Avg Min SNR: {eval_metrics['avg_bottleneck_snr']:.2f} | "
                f"SNR Var: {eval_metrics['avg_snr_variance']:.2f}"
            )
            policy_net.train()

    # 6. 保存模型
    os.makedirs(args.save_dir, exist_ok=True)
    save_path = os.path.join(args.save_dir, "uav_policy_final.pt")
    torch.save(
        {
            "policy_state_dict": policy_net.state_dict(),
            "encoder_state_dict": encoder.state_dict(),
            "embedding_dim": args.embedding_dim,
            "gru_hidden_dim": args.gru_hidden_dim,
        },
        save_path,
    )
    print(f"--- 训练完成，模型保存至: {save_path} ---")


if __name__ == "__main__":
    main()
