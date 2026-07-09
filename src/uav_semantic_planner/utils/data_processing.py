"""
数据处理与转换模块

本模块提供用于将加载后的原始图谱数据转换为模型所需格式的函数。
数据加载功能请参阅 `data_loader.py`。
"""

import os
from collections import defaultdict, deque

import networkx as nx
import torch
from torch_geometric.data import Data
from torch_geometric.utils import to_networkx

from uav_semantic_planner.data.data_loader import KnowledgeGraph

# --- 动态导入 ---
try:
    import cudf
    import cugraph

    HAS_CUGRAPH = True
except ImportError:
    cudf = None
    cugraph = None
    HAS_CUGRAPH = False

from typing import Any

# --- 类型注释 ---
EntityMap = dict[str, int]
RelationMap = dict[str, int]
NodeMap = dict[int, str]


def pyg_to_cugraph(pyg_data: Data, directed: bool = True) -> Any | None:
    """将 PyG Data 转换为 cuGraph (GPU加速)"""
    if not HAS_CUGRAPH or pyg_data.edge_index.device.type != "cuda":
        return None
    try:
        source_nodes = pyg_data.edge_index[0]
        target_nodes = pyg_data.edge_index[1]
        edge_df = cudf.DataFrame({"source": source_nodes, "destination": target_nodes})
        G = cugraph.Graph(directed=directed)
        G.from_cudf_edgelist(
            edge_df, source="source", destination="destination", store_transposed=True
        )
        return G
    except Exception as e:
        print(f"--- 警告: cuGraph 转换失败: {e} ---")
        return None


def calculate_pagerank(data: Data) -> dict[int, float]:
    """使用 GPU (cuGraph) 或 CPU (NetworkX) 计算 PageRank"""
    print("--- 正在计算 PageRank ---")
    if torch.cuda.is_available() and HAS_CUGRAPH:
        data_gpu = data.to("cuda") if data.edge_index.device.type == "cpu" else data
        G = pyg_to_cugraph(data_gpu, directed=True)
        if G is not None:
            try:
                pr = cugraph.pagerank(G, alpha=0.85, max_iter=100, tol=1e-6)
                return {
                    int(row["vertex"]): float(row["pagerank"])
                    for _, row in pr.to_pandas().iterrows()
                }
            except Exception:
                pass

    # 回退到 CPU
    G_nx = to_networkx(data.cpu(), to_undirected=False)
    return nx.pagerank(G_nx, alpha=0.85, max_iter=100, tol=1e-6)


import json


def save_mappings(entity_map, relation_map, entity_map_path, relation_map_path):
    """保存节点和关系映射"""
    os.makedirs(os.path.dirname(entity_map_path), exist_ok=True)
    with open(entity_map_path, "w", encoding="utf-8") as f:
        json.dump(entity_map, f, ensure_ascii=False, indent=4)
    with open(relation_map_path, "w", encoding="utf-8") as f:
        json.dump(relation_map, f, ensure_ascii=False, indent=4)


def process_uav_graph(
    kg_data: KnowledgeGraph,
    existing_node_map: dict[str, str] = None,
    existing_relation_map: RelationMap = None,
    existing_node_id_map: dict[str, int] = None,
    snr_threshold: float = 5.0,
) -> tuple[
    Data,
    NodeMap,
    RelationMap,
    dict[int, float],
    torch.Tensor,
    dict[tuple[int, int], float],
    set[tuple[int, int]],
    dict[int, str],
]:
    """
    处理无人机通信网络图谱，提取异构类型和 SNR 特征。

    Args:
        kg_data: 原始知识图谱数据
        existing_node_map: 已有的节点映射 (int_id -> name)
        existing_relation_map: 已有的关系映射
        existing_node_id_map: 已有的原始 ID 映射 (raw_id -> int_id)
        snr_threshold: 判断弱链路的信噪比阈值

    Returns:
        (Data, node_map, relation_map, pagerank_values, node_types, snr_map, weak_link_set, int_id_to_raw_id)
    """
    print("--- 正在处理 UAV 通信网络图谱数据 (支持异构类型与 ID 对齐) ---")
    nodes = kg_data["nodes"]
    edges = kg_data["edges"]

    id_to_id = {}  # raw_id -> int_id
    node_map = {}  # int_id -> name
    int_id_to_raw_id = {}  # int_id -> raw_id

    # 1. 建立节点 ID 映射
    if existing_node_id_map:
        print("  - 发现 existing_node_id_map，执行精确对齐")
        id_to_id = {str(k): int(v) for k, v in existing_node_id_map.items()}
        for node in nodes:
            raw_id = node["id"]
            if raw_id in id_to_id:
                new_id = id_to_id[raw_id]
                node_map[new_id] = node["name"]
                int_id_to_raw_id[new_id] = raw_id
    else:
        # 初始化：全新的映射
        print("  - 初始化全新节点映射")
        node_ids = sorted([node["id"] for node in nodes])
        for i, raw_id in enumerate(node_ids):
            id_to_id[raw_id] = i
            node_name = next(n["name"] for n in nodes if n["id"] == raw_id)
            node_map[i] = node_name
            int_id_to_raw_id[i] = raw_id

    num_nodes = len(node_map)
    old_id_to_new_id = {node["id"]: id_to_id.get(node["id"]) for node in nodes}

    # --- 动态映射节点类型 ---
    all_possible_types = ["GND-C", "BS", "UAV-R", "UAV-M", "GND-P", "UAV-S"]
    type_to_id = {t: i for i, t in enumerate(all_possible_types)}
    node_types = torch.zeros(num_nodes, dtype=torch.long)
    for node in nodes:
        new_id = old_id_to_new_id.get(node["id"])
        if new_id is not None:
            node_types[new_id] = type_to_id.get(node.get("type", "GND-P"), 0)

    # --- 关系映射 ---
    if existing_relation_map:
        relation_map = existing_relation_map
    else:
        unique_relations = sorted(list(set(edge["relation"] for edge in edges)))
        relation_map = {rel: i for i, rel in enumerate(unique_relations)}

    # 建立边和 SNR/弱链路特征
    edge_index_list, edge_relations = [], []
    snr_map = {}  # (src_id, tgt_id) -> snr_value
    weak_link_set = set()  # (src_id, tgt_id)

    # 记录特殊关系ID
    disconn_rel_id = relation_map.get("DISCONN", -1)

    for edge in edges:
        src_new, tgt_new = (
            old_id_to_new_id.get(edge["source"]),
            old_id_to_new_id.get(edge["target"]),
        )
        rel_name = edge["relation"]
        snr_val = edge.get("snr", 0.0)

        if src_new is not None and tgt_new is not None and rel_name in relation_map:
            edge_index_list.append([src_new, tgt_new])

            rel_id = relation_map[rel_name]
            edge_relations.append(rel_id)

            # 构建 SNR 特征
            snr_map[(src_new, tgt_new)] = snr_val

            # 识别弱链路（根据关系类型或 SNR 值）
            if rel_id == disconn_rel_id or snr_val < snr_threshold:
                weak_link_set.add((src_new, tgt_new))

    edge_index = torch.tensor(edge_index_list, dtype=torch.long).t().contiguous()
    edge_type = torch.tensor(edge_relations, dtype=torch.long)

    # 计算全局图拓扑势能
    pagerank_values = calculate_pagerank(
        Data(edge_index=edge_index, num_nodes=num_nodes)
    )

    data = Data(edge_index=edge_index, edge_type=edge_type, num_nodes=num_nodes)

    return (
        data,
        node_map,
        relation_map,
        pagerank_values,
        node_types,
        snr_map,
        weak_link_set,
        int_id_to_raw_id,
    )


def convert_to_hetero(
    data: Data,
    node_types: torch.Tensor,
    edge_type: torch.Tensor,
    relation_map: dict[str, int],
) -> tuple[dict[str, torch.Tensor], dict[tuple, torch.Tensor], tuple]:
    """
    将同构图 Data 转换为异构图结构，返回 HGT 预期的三元组。
    """
    # 定义 UAV 标准类型顺序
    all_possible_types = ["GND-C", "BS", "UAV-R", "UAV-M", "GND-P", "UAV-S"]

    # 识别当前子图中实际存在的类型 ID
    unique_type_ids = torch.unique(node_types).tolist()
    node_type_names = {tid: all_possible_types[tid] for tid in unique_type_ids}

    x_dict_ids = {}
    edge_index_dict = {}
    global_to_local = torch.zeros(node_types.size(0), dtype=torch.long)

    # 1. 建立节点字典
    for type_id in unique_type_ids:
        type_name = node_type_names[type_id]
        mask = node_types == type_id
        indices = torch.where(mask)[0]
        x_dict_ids[type_name] = indices
        global_to_local[indices] = torch.arange(len(indices))

    # 2. 建立边字典 (按三元组拆分)
    inv_rel_map = {v: k for k, v in relation_map.items()}
    src_nodes, dst_nodes = data.edge_index[0], data.edge_index[1]

    temp_edge_dict = {}  # (s_type, rel, d_type) -> [[src], [dst]]

    print(f"--- 正在构建异构边映射 (共 {data.num_edges} 条边) ---")
    for i in range(data.num_edges):
        rel_id = edge_type[i].item()
        rel_name = inv_rel_map[rel_id]

        u, v = src_nodes[i].item(), dst_nodes[i].item()
        u_type = node_type_names[node_types[u].item()]
        v_type = node_type_names[node_types[v].item()]

        key = (u_type, rel_name, v_type)
        if key not in temp_edge_dict:
            temp_edge_dict[key] = [[], []]

        temp_edge_dict[key][0].append(global_to_local[u].item())
        temp_edge_dict[key][1].append(global_to_local[v].item())

    # 转换为 Tensor 格式
    for key, val in temp_edge_dict.items():
        edge_index_dict[key] = torch.tensor(val, dtype=torch.long)

    metadata = (list(x_dict_ids.keys()), list(edge_index_dict.keys()))
    return x_dict_ids, edge_index_dict, metadata


def clean_graph(data, report=True):
    if data is None or not hasattr(data, "edge_index"):
        return data
    edge_index, edge_type = data.edge_index, getattr(data, "edge_type", None)
    cleaned_pairs, cleaned_types, seen = [], [], set()
    for idx in range(edge_index.shape[1]):
        s, t = edge_index[0, idx].item(), edge_index[1, idx].item()
        if s == t or (s, t) in seen:
            continue
        seen.add((s, t))
        cleaned_pairs.append([s, t])
        if edge_type is not None:
            cleaned_types.append(edge_type[idx].item())
    new_data = Data(
        edge_index=torch.tensor(cleaned_pairs, dtype=torch.long).t().contiguous(),
        edge_type=torch.tensor(cleaned_types, dtype=torch.long),
        num_nodes=data.num_nodes,
    )
    if report:
        print(f"--- clean_graph: edges {edge_index.shape[1]} -> {new_data.num_edges}")
    return new_data


def filter_reachable_pairs(pairs, data, max_pairs=None, report=True):
    adj = defaultdict(list)
    for i in range(data.edge_index.shape[1]):
        adj[data.edge_index[0, i].item()].append(data.edge_index[1, i].item())
    reachable = []
    for s, t in pairs:
        if s == t:
            reachable.append((s, t))
        else:
            q, v = deque([s]), {s}
            while q:
                c = q.popleft()
                if any(nb == t for nb in adj.get(c, [])):
                    reachable.append((s, t))
                    break
                for nb in adj.get(c, []):
                    if nb not in v:
                        v.add(nb)
                        q.append(nb)
        if max_pairs and len(reachable) >= max_pairs:
            break
    if report:
        print(f"--- filter_reachable_pairs: {len(reachable)}/{len(pairs)} reachable")
    return reachable, len(pairs) - len(reachable)
