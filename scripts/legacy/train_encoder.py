"""
Pre-HGT 编码器预训练脚本 (V2.6 兼容 PyTorch 2.6)
"""

import argparse
import os

import torch
import torch.nn.functional as F
import torch.optim as optim
from hgt_rl_planner.data_loader import (
    load_custom_kg_from_json,
    load_mooccubex_subgraph,
)
from hgt_rl_planner.models import PreHGTEncoder
from hgt_rl_planner.utils.data_processing import (
    convert_to_hetero,
    process_custom_kg,
)
from hgt_rl_planner.utils.seeding import set_seed
from torch.cuda.amp import GradScaler, autocast
from torch_geometric.utils import negative_sampling


class HGCTrainer:
    def __init__(
        self,
        encoder: PreHGTEncoder,
        device: torch.device,
        learning_rate: float,
        x_dict_ids: dict[str, torch.Tensor],
        prereq_index: torch.Tensor | None = None,
        use_amp: bool = True,
        weight_decay: float = 0.0,
    ):
        self.encoder = encoder
        self.device = device
        self.optimizer = optim.Adam(
            encoder.parameters(), lr=learning_rate, weight_decay=weight_decay
        )
        self.x_dict_ids = x_dict_ids
        self.prereq_index = prereq_index
        self.use_amp = use_amp and device.type == "cuda"
        self.scaler = GradScaler() if self.use_amp else None

    def train_epoch(self, x_dict, edge_index_dict, data, neg_sample_ratio) -> float:
        self.encoder.train()
        self.optimizer.zero_grad()

        if self.use_amp:
            with autocast():
                z_dict = self.encoder(
                    x_dict, edge_index_dict, prereq_index=self.prereq_index
                )
                any_emb = next(iter(z_dict.values()))
                z = torch.zeros((data.num_nodes, any_emb.size(1)), device=self.device)
                for nt, indices in self.x_dict_ids.items():
                    z[indices] = z_dict[nt]
                pos_edge_index = data.edge_index
                # 使用 dense 方法提升训练速度（适用于 5000 节点的中等规模图）
                neg_edge_index = negative_sampling(
                    edge_index=data.edge_index,
                    num_nodes=data.num_nodes,
                    num_neg_samples=int(pos_edge_index.size(1) * neg_sample_ratio),
                    method="dense",
                )
                pos_logits = (z[pos_edge_index[0]] * z[pos_edge_index[1]]).sum(dim=1)
                neg_logits = (z[neg_edge_index[0]] * z[neg_edge_index[1]]).sum(dim=1)
                loss = F.binary_cross_entropy_with_logits(
                    pos_logits, torch.ones_like(pos_logits)
                ) + F.binary_cross_entropy_with_logits(
                    neg_logits, torch.zeros_like(neg_logits)
                )

            self.scaler.scale(loss).backward()
            self.scaler.step(self.optimizer)
            self.scaler.update()
        else:
            z_dict = self.encoder(
                x_dict, edge_index_dict, prereq_index=self.prereq_index
            )
            any_emb = next(iter(z_dict.values()))
            z = torch.zeros((data.num_nodes, any_emb.size(1)), device=self.device)
            for nt, indices in self.x_dict_ids.items():
                z[indices] = z_dict[nt]
            pos_edge_index = data.edge_index
            # 使用 dense 方法提升训练速度（适用于 5000 节点的中等规模图）
            neg_edge_index = negative_sampling(
                edge_index=data.edge_index,
                num_nodes=data.num_nodes,
                num_neg_samples=int(pos_edge_index.size(1) * neg_sample_ratio),
                method="dense",
            )
            pos_logits = (z[pos_edge_index[0]] * z[pos_edge_index[1]]).sum(dim=1)
            neg_logits = (z[neg_edge_index[0]] * z[neg_edge_index[1]]).sum(dim=1)
            loss = F.binary_cross_entropy_with_logits(
                pos_logits, torch.ones_like(pos_logits)
            ) + F.binary_cross_entropy_with_logits(
                neg_logits, torch.zeros_like(neg_logits)
            )
            loss.backward()
            self.optimizer.step()

        return loss.item()


def main(args):
    device = torch.device(
        "cuda" if torch.cuda.is_available() and args.use_cuda else "cpu"
    )
    print(f"--- [HGT Pretrain] 使用设备: {device} ---")
    set_seed(args.seed, force_deterministic=True)

    # 使用字段特定的 kg_data_{field}.json，确保领域隔离
    kg_json_path = os.path.join(args.data_dir, f"kg_data_{args.field}.json")
    if os.path.exists(kg_json_path):
        kg_data = load_custom_kg_from_json(kg_json_path)
    elif "MOOCCubex" in args.data_dir:
        kg_data, _ = load_mooccubex_subgraph(args.data_dir, target_field=args.field)
    else:
        raise FileNotFoundError(
            f"未找到领域 [{args.field}] 的知识图谱数据: {kg_json_path}"
        )

    data, entity_map, relation_map, _, node_types, prereq_map, int_id_to_raw_id = (
        process_custom_kg(kg_data)
    )
    data = data.to(device)
    node_types = node_types.to(device)
    x_dict_ids, edge_index_dict, metadata = convert_to_hetero(
        data, node_types, data.edge_type, relation_map
    )
    edge_index_dict = {k: v.to(device) for k, v in edge_index_dict.items()}
    x_dict = {k: torch.arange(len(v), device=device) for k, v in x_dict_ids.items()}
    global_to_hgt_local, current_offset = {}, 0
    for nt in ["Theory", "Method", "Application", "Tool"]:
        if nt in x_dict_ids:
            for l_idx, g_idx in enumerate(x_dict_ids[nt]):
                global_to_hgt_local[g_idx.item()] = current_offset + l_idx
            current_offset += len(x_dict_ids[nt])
    prereq_sources, prereq_targets = [], []
    for target_g, sources in prereq_map.items():
        if target_g in global_to_hgt_local:
            t_l = global_to_hgt_local[target_g]
            for s_g in sources:
                if s_g in global_to_hgt_local:
                    prereq_sources.append(global_to_hgt_local[s_g])
                    prereq_targets.append(t_l)
    prereq_index = (
        torch.tensor([prereq_sources, prereq_targets], dtype=torch.long, device=device)
        if prereq_sources
        else None
    )
    num_nodes_dict = {k: len(v) for k, v in x_dict_ids.items()}
    node_types_order = ["Theory", "Method", "Application", "Tool"]
    encoder = PreHGTEncoder(
        num_nodes_dict,
        args.embedding_dim,
        args.hidden_channels,
        args.out_channels,
        metadata,
        heads=args.heads,
        node_types_order=node_types_order,
    ).to(device)
    trainer = HGCTrainer(
        encoder,
        device,
        args.learning_rate,
        x_dict_ids,
        prereq_index=prereq_index,
        use_amp=args.use_amp,
        weight_decay=args.weight_decay,
    )
    if args.use_amp and device.type == "cuda":
        print("--- [HGT Pretrain] 已启用自动混合精度训练 (AMP) ---")
    for epoch in range(1, args.epochs + 1):
        loss = trainer.train_epoch(x_dict, edge_index_dict, data, args.neg_sample_ratio)
        if epoch % 100 == 0:
            print(f"Epoch: {epoch:04d}, Loss: {loss:.4f}")
    os.makedirs(os.path.dirname(args.save_path), exist_ok=True)
    encoder.eval()
    with torch.no_grad():
        z_dict = encoder(x_dict, edge_index_dict, prereq_index=prereq_index)
        any_emb = next(iter(z_dict.values()))
        z = torch.zeros((data.num_nodes, any_emb.size(1)), device=device)
        for nt, indices in x_dict_ids.items():
            z[indices] = z_dict[nt]

    # --- [关键] 强制转换 defaultdict 为标准 dict 以支持 PyTorch 2.6 weights_only=True ---
    serializable_prereq = {int(k): list(v) for k, v in prereq_map.items()}

    torch.save(
        {
            "model_state_dict": encoder.state_dict(),
            "node_embeddings": z.cpu(),
            "entity_map": entity_map,
            "relation_map": relation_map,
            "raw_id_map": int_id_to_raw_id,
            "node_types": node_types.cpu(),
            "prereq_map": serializable_prereq,
        },
        args.save_path,
    )
    print(f"--- [HGT Final] Checkpoint 已存至: {args.save_path} ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, default="data/MOOCCubex")
    parser.add_argument("--field", type=str, default="心理学")
    parser.add_argument(
        "--dataset_type", type=str, default="mooc", choices=["mooc", "standard"]
    )
    parser.add_argument("--dataset_name", type=str, default="MOOCCubex")
    parser.add_argument(
        "--save_path", type=str, default="checkpoints/MOOCCubex/hgt_mooccubex.pt"
    )
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--embedding_dim", type=int, default=128)
    parser.add_argument("--hidden_channels", type=int, default=64)
    parser.add_argument("--out_channels", type=int, default=128)
    parser.add_argument("--heads", type=int, default=4, help="HGT 注意力头数量")
    parser.add_argument("--learning_rate", type=float, default=0.001)
    parser.add_argument(
        "--weight_decay", type=float, default=0.0, help="Adam 优化器的权重衰减"
    )
    parser.add_argument("--neg_sample_ratio", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--use_cuda", action="store_true")
    parser.add_argument("--print_every", type=int, default=10)
    parser.add_argument("--force_deterministic", action="store_true")
    parser.add_argument(
        "--use_amp", action="store_true", help="启用自动混合精度训练 (AMP)"
    )
    args = parser.parse_args()

    # 动态构建保存路径（针对 standard 数据集）
    if args.dataset_type == "standard" and args.dataset_name:
        args.data_dir = f"data/{args.dataset_name}"
        args.save_path = f"checkpoints/{args.dataset_name}/hgt_{args.dataset_name}.pt"
        os.makedirs(os.path.dirname(args.save_path), exist_ok=True)

    main(args)
