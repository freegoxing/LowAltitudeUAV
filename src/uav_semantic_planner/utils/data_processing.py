"""
数据处理与转换模块

本模块提供用于将加载后的原始数据转换为模型所需格式的函数。
数据加载功能请参阅 `data_loader.py`。
"""

import json
import os
from collections import defaultdict, deque

import networkx as nx
import torch
from torch_geometric.data import Data
from torch_geometric.utils import to_networkx

from hgt_rl_planner.data_loader import KnowledgeGraph

# --- 动态导入 ---
try:
    import cudf
    import cugraph

    HAS_CUGRAPH = True
except ImportError:
    cudf = None
    cugraph = None
    HAS_CUGRAPH = False

# --- 类型注释 ---
EntityMap = dict[str, int]
RelationMap = dict[str, int]
NodeMap = dict[int, str]
IntTriplets = list[tuple[int, int, int]]


def pyg_to_cugraph(pyg_data: Data, directed: bool = True) -> any | None:
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


def save_mappings(entity_map, relation_map, entity_map_path, relation_map_path):
    """保存节点和关系映射"""
    os.makedirs(os.path.dirname(entity_map_path), exist_ok=True)
    with open(entity_map_path, "w", encoding="utf-8") as f:
        json.dump(entity_map, f, ensure_ascii=False, indent=4)
    with open(relation_map_path, "w", encoding="utf-8") as f:
        json.dump(relation_map, f, ensure_ascii=False, indent=4)


def process_custom_kg(
    kg_data: KnowledgeGraph,
    existing_node_map: dict[str, str] = None,
    existing_relation_map: RelationMap = None,
    existing_node_id_map: dict[str, int] = None,
) -> tuple[
    Data,
    NodeMap,
    RelationMap,
    dict[int, float],
    torch.Tensor,
    dict[int, set[int]],
    dict[int, str],
]:
    """
    处理自定义图，提取异构类型和先修关系。

    Args:
        kg_data: 原始知识图谱数据
        existing_node_map: 已有的节点映射 (int_id -> name)
        existing_relation_map: 已有的关系映射
        existing_node_id_map: 已有的原始 ID 映射 (raw_id -> int_id)

    Returns:
        (Data, node_map, relation_map, pagerank_values, node_types, prerequisite_map, int_id_to_raw_id)
    """
    print("--- 正在处理自定义知识图谱数据 (支持异构类型与 ID 对齐) ---")
    nodes = kg_data["nodes"]
    edges = kg_data["edges"]

    id_to_id = {}  # raw_id -> int_id
    node_map = {}  # int_id -> name
    int_id_to_raw_id = {}  # int_id -> raw_id

    # 1. 建立节点 ID 映射
    if existing_node_id_map:
        # 优先级最高：基于原始 ID 对齐
        print("  - 发现 existing_node_id_map，执行基于 Raw ID 的精确对齐")
        id_to_id = {str(k): int(v) for k, v in existing_node_id_map.items()}
        for node in nodes:
            raw_id = node["id"]
            if raw_id in id_to_id:
                new_id = id_to_id[raw_id]
                node_map[new_id] = node["name"]
                int_id_to_raw_id[new_id] = raw_id
            else:
                # 处理新节点（如果增量更新支持的话，目前仅作记录）
                pass
    elif existing_node_map:
        # 降级：基于名称对齐（风险：重名节点塌缩）
        print(
            "  - 警告：未发现 existing_node_id_map，回退到基于名称对齐 (存在重名塌缩风险)"
        )
        old_node_map = {int(k): v for k, v in existing_node_map.items()}

        # 构建 name -> list of old_ids 映射
        name_to_old_ids = defaultdict(list)
        for k, v in old_node_map.items():
            name_to_old_ids[v].append(k)

        conflict_names = [name for name, ids in name_to_old_ids.items() if len(ids) > 1]
        if conflict_names:
            print(f"  - !!! 强告警：检测到 {len(conflict_names)} 个重名冲突概念！")
            for name in conflict_names[:5]:  # 仅列出前5个
                print(f"    - 冲突名称: '{name}', 对应旧 IDs: {name_to_old_ids[name]}")

        # 尝试匹配
        used_old_ids = set()
        for node in nodes:
            name = node["name"]
            raw_id = node["id"]
            if name in name_to_old_ids:
                # 尽量按顺序分配（这只是启发式，不能保证完全正确，除非 raw_id 一致）
                potential_ids = [
                    oid for oid in name_to_old_ids[name] if oid not in used_old_ids
                ]
                if potential_ids:
                    target_id = potential_ids[0]
                    id_to_id[raw_id] = target_id
                    node_map[target_id] = name
                    int_id_to_raw_id[target_id] = raw_id
                    used_old_ids.add(target_id)
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
    # 再次确保所有当前节点都有映射
    old_id_to_new_id = {node["id"]: id_to_id.get(node["id"]) for node in nodes}

    # --- 动态映射类型 ---
    all_possible_types = ["Theory", "Method", "Application", "Tool"]
    type_to_id = {t: i for i, t in enumerate(all_possible_types)}
    node_types = torch.zeros(num_nodes, dtype=torch.long)
    for node in nodes:
        new_id = old_id_to_new_id.get(node["id"])
        if new_id is not None:
            node_types[new_id] = type_to_id.get(node.get("type", "Theory"), 0)

    if existing_relation_map:
        relation_map = existing_relation_map
    else:
        unique_relations = sorted(list(set(edge["relation"] for edge in edges)))
        relation_map = {rel: i for i, rel in enumerate(unique_relations)}

    # 建立边和先修关系
    edge_index_list, edge_relations = [], []
    prerequisite_map = defaultdict(set)
    prereq_rel_names = {"precede", "requires", "prerequisite", "先修"}

    for edge in edges:
        src_new, tgt_new = (
            old_id_to_new_id.get(edge["source"]),
            old_id_to_new_id.get(edge["target"]),
        )
        rel_name = edge["relation"]
        if src_new is not None and tgt_new is not None and rel_name in relation_map:
            edge_index_list.append([src_new, tgt_new])
            edge_relations.append(relation_map[rel_name])
            if rel_name.lower() in prereq_rel_names:
                prerequisite_map[tgt_new].add(src_new)

    edge_index = torch.tensor(edge_index_list, dtype=torch.long).t().contiguous()
    edge_type = torch.tensor(edge_relations, dtype=torch.long)
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
        prerequisite_map,
        int_id_to_raw_id,
    )


def process_standard_kg(train_triplets, valid_triplets, test_triplets):
    """处理标准三元组数据集 (如 FB15k-237)"""
    print("--- 正在处理标准知识图谱数据 ---")
    all_triplets = train_triplets + valid_triplets + test_triplets
    entities = sorted(
        list(set(h for h, r, t in all_triplets) | set(t for h, r, t in all_triplets))
    )
    relations = sorted(list(set(r for h, r, t in all_triplets)))

    ent_map = {name: i for i, name in enumerate(entities)}
    rel_map = {name: i for i, name in enumerate(relations)}
    num_ent, num_rel = len(ent_map), len(rel_map)

    def to_int(trips):
        return [(ent_map[h], rel_map[r], ent_map[t]) for h, r, t in trips]

    t_int, v_int, ts_int = (
        to_int(train_triplets),
        to_int(valid_triplets),
        to_int(test_triplets),
    )

    edge_index, edge_type = [], []
    for h, r, t in t_int:
        edge_index.append([h, t])
        edge_type.append(r)
        edge_index.append([t, h])
        edge_type.append(r + num_rel)  # 反向边

    data = Data(
        edge_index=torch.tensor(edge_index, dtype=torch.long).t().contiguous(),
        edge_type=torch.tensor(edge_type, dtype=torch.long),
        num_nodes=num_ent,
    )

    return data, ent_map, rel_map, t_int, v_int, ts_int


def convert_to_hetero(
    data: Data,
    node_types: torch.Tensor,
    edge_type: torch.Tensor,
    relation_map: dict[str, int],
) -> tuple[dict[str, torch.Tensor], dict[tuple, torch.Tensor], tuple]:
    """
    将同构图 Data 转换为异构图结构，返回 train_hgt.py 预期的三元组。
    修复版：支持一种关系名连接多种不同类型的节点组合。
    """
    # 定义标准类型顺序
    all_possible_types = ["Theory", "Method", "Application", "Tool"]

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
