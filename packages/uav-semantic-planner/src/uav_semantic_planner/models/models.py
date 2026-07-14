"""
UAV 语义通信网络模型定义模块

职责：
- 定义 UAVHGTEncoder 编码器：集成弱链路/断连预警惩罚注入。
- 定义 RLPolicyNet (Actor-Critic)：基于通信特征进行路由规划。
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import HGTConv, RGCNConv


class UAVHGTEncoder(nn.Module):
    """
    态势感知异构图 Transformer (UAV-HGT) 编码器。

    支持对弱通信链路 (Weak Links) 的惩罚注入，将态势感知特征融入拓扑。
    """

    def __init__(
        self,
        num_nodes_dict: dict[str, int],
        embedding_dim: int,
        hidden_channels: int,
        out_channels: int,
        metadata: tuple[list[str], list[tuple[str, str, str]]],
        heads: int = 4,
        use_weak_link_injection: bool = True,
        use_layer_norm: bool = True,
        use_dropout: bool = True,
        use_multihead: bool = True,
        node_types_order: list[str] | None = None,
    ):
        super().__init__()
        self.use_weak_link_injection = use_weak_link_injection
        self.use_layer_norm = use_layer_norm
        self.use_dropout = use_dropout

        # 默认使用 UAV 领域的节点类型排序
        default_order = ["GND-C", "BS", "UAV-R", "UAV-M", "GND-P"]
        self.node_types_order = node_types_order or default_order

        # 确定头数
        hgt_heads = heads if use_multihead else 1

        # 异构节点嵌入层
        self.node_emb_dict = nn.ModuleDict(
            {
                node_type: nn.Embedding(num_count, embedding_dim)
                for node_type, num_count in num_nodes_dict.items()
            }
        )

        # 异构 Transformer 层 1
        self.hgt1 = HGTConv(embedding_dim, hidden_channels, metadata, heads=hgt_heads)
        if use_layer_norm:
            self.norm1 = nn.LayerNorm(hidden_channels)

        # 异构 Transformer 层 2
        self.hgt2 = HGTConv(hidden_channels, out_channels, metadata, heads=hgt_heads)
        if use_layer_norm:
            self.norm2 = nn.LayerNorm(out_channels)

        if use_dropout:
            self.dropout = nn.Dropout(0.4)

    def forward(
        self,
        x_dict: dict[str, torch.Tensor],
        edge_index_dict: dict[tuple[str, str, str], torch.Tensor],
        weak_link_index: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """
        向量化前向传播：Embedding -> Weak Link Injection -> HGT Layers
        """
        # 1. 获取初始嵌入
        # x_dict 传入的可能是全局索引，而 Embedding 层的大小是局部数量
        h_dict = {}
        for nt in x_dict.keys():
            device = x_dict[nt].device
            num_nodes = self.node_emb_dict[nt].num_embeddings
            h_dict[nt] = self.node_emb_dict[nt](torch.arange(num_nodes, device=device))

        # 2. 弱链路惩罚注入 (Weak Link Injection)
        # 将被标记为弱链路（SNR差或预警）的影响注入节点嵌入中
        if (
            self.use_weak_link_injection
            and weak_link_index is not None
            and weak_link_index.numel() > 0
        ):
            all_h = []
            active_types = []
            for nt in self.node_types_order:
                if nt in h_dict:
                    all_h.append(h_dict[nt])
                    active_types.append(nt)

            if all_h:
                combined_h = torch.cat(all_h, dim=0)
                src, dst = weak_link_index[0], weak_link_index[1]

                num_total_nodes = combined_h.size(0)
                sum_features = torch.zeros_like(combined_h)

                valid_mask = (src < num_total_nodes) & (dst < num_total_nodes)
                src_v, dst_v = src[valid_mask], dst[valid_mask]

                sum_features.index_add_(0, dst_v, combined_h[src_v])

                counts = torch.zeros(
                    num_total_nodes, device=combined_h.device
                ).index_add_(0, dst_v, torch.ones_like(dst_v, dtype=torch.float))
                counts = torch.clamp(counts, min=1.0).unsqueeze(1)
                avg_weak_h = sum_features / counts

                # 区别于先修约束的正向融合(+)，这里使用反向推离(-)来惩罚弱链路相连的节点
                # 迫使注意力机制主动疏远此类节点
                offset = 0
                for nt in active_types:
                    num_nt = h_dict[nt].size(0)
                    h_dict[nt] = h_dict[nt] - torch.tanh(
                        avg_weak_h[offset : offset + num_nt]
                    )
                    offset += num_nt

        # 3. 第一层 HGT + 正则
        h_dict = self.hgt1(h_dict, edge_index_dict)

        for k in h_dict.keys():
            x = F.gelu(h_dict[k])
            if self.use_layer_norm:
                x = self.norm1(x)
            if self.use_dropout:
                x = self.dropout(x)
            h_dict[k] = x

        # 4. 第二层 HGT + 正则
        h_dict = self.hgt2(h_dict, edge_index_dict)
        if self.use_layer_norm:
            h_dict = {k: self.norm2(v) for k, v in h_dict.items()}

        return h_dict


class RLPolicyNet(nn.Module):
    """
    强化学习策略网络 (Actor-Critic)。
    职责: 基于预训练好的异构嵌入进行通信路径规划决策。
    已优化: 支持批量化 (Batched) 前向传播。
    """

    def __init__(self, embedding_dim: int, gru_hidden_dim: int):
        super().__init__()
        self.embedding_dim = embedding_dim
        self.gru_hidden_dim = gru_hidden_dim

        # 路径记忆单元 (GRUCell 支持 batch)
        self.gru_cell = nn.GRUCell(embedding_dim, gru_hidden_dim)

        # Actor: 策略头
        self.policy_head = nn.Sequential(
            nn.Linear(gru_hidden_dim + embedding_dim * 2, 256),
            nn.LayerNorm(256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 1),
        )

        # Critic: 价值头
        self.value_head = nn.Sequential(
            nn.Linear(gru_hidden_dim + embedding_dim, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Linear(128, 1),
        )

    def forward(
        self,
        current_emb: torch.Tensor,
        target_emb: torch.Tensor,
        neighbor_embs: torch.Tensor,
        path_memory: torch.Tensor,
        neighbor_mask: torch.Tensor | None = None,
    ) -> tuple[torch.distributions.Categorical | None, torch.Tensor, torch.Tensor]:
        """
        计算策略分布与状态价值。
        自动处理单实例/批量维度的对齐。
        """
        if current_emb.dim() == 1:
            current_emb = current_emb.unsqueeze(0)
        if target_emb.dim() == 1:
            target_emb = target_emb.unsqueeze(0)
        if path_memory.dim() == 1:
            path_memory = path_memory.unsqueeze(0)
        if neighbor_embs is not None and neighbor_embs.dim() == 2:
            neighbor_embs = neighbor_embs.unsqueeze(0)
            if neighbor_mask is not None and neighbor_mask.dim() == 1:
                neighbor_mask = neighbor_mask.unsqueeze(0)

        # 更新路径记忆
        next_path_memory = self.gru_cell(current_emb, path_memory)

        # 计算价值 (Value)
        value_input = torch.cat([next_path_memory, target_emb], dim=-1)
        state_value = self.value_head(value_input)

        # 计算动作概率 (Policy)
        if neighbor_embs is None or neighbor_embs.size(1) == 0:
            return None, state_value, next_path_memory

        max_neighbors = neighbor_embs.size(1)

        memory_expanded = next_path_memory.unsqueeze(1).expand(-1, max_neighbors, -1)
        target_expanded = target_emb.unsqueeze(1).expand(-1, max_neighbors, -1)

        policy_input = torch.cat(
            [memory_expanded, neighbor_embs, target_expanded], dim=-1
        )

        action_scores = self.policy_head(policy_input).squeeze(-1)

        if neighbor_mask is not None:
            action_scores = action_scores.masked_fill(neighbor_mask == 0, -1e4)

        action_dist = torch.distributions.Categorical(logits=action_scores)

        return action_dist, state_value, next_path_memory


class RGCNEncoder(nn.Module):
    """基础 R-GCN 编码器作为对比基准"""

    def __init__(
        self, num_nodes, embedding_dim, hidden_channels, out_channels, num_relations
    ):
        super().__init__()
        self.embedding = nn.Embedding(num_nodes, embedding_dim)
        self.rgcn1 = RGCNConv(embedding_dim, hidden_channels, num_relations)
        self.rgcn2 = RGCNConv(hidden_channels, out_channels, num_relations)
        self.dropout = nn.Dropout(0.5)

    def forward(self, edge_index, edge_type):
        x = self.embedding.weight
        x = F.relu(self.rgcn1(x, edge_index, edge_type))
        x = self.dropout(x)
        x = self.rgcn2(x, edge_index, edge_type)
        return x
