"""
UAV 语义通信网络数据加载模块

本模块负责从磁盘读取低空无人机通信网络的图谱数据（JSON 格式）。
模块内不包含任何数据清洗、预处理或结构转换逻辑，
相关处理功能请参阅 `utils/data_processing.py`。

该模块为后续的 HGT 编码与强化学习训练流程
提供统一、可靠的数据输入接口。
"""

import json
from typing import Any


# --- 类型注释 ---
class NodesData(dict[str, Any]):
    """单个节点的结构定义

    期望字段:
        id (str): 全局唯一标识，如 "UAV-M-1"
        name (str): 节点名称
        type (str): 节点类型，取值 GND-C / BS / UAV-R / UAV-M / GND-P
        desc (str): 描述信息
        battery (float): 剩余电量 [0, 1]
        capacity (int): 通信容量
        snr_uplink (float): 上行信噪比均值 (dB)
        snr_downlink (float): 下行信噪比均值 (dB)
        connected_links_count (int): 当前连接的链路数量
    """

    pass


class EdgesData(dict[str, Any]):
    """单条边的结构定义

    期望字段:
        source (str): 源节点 ID
        target (str): 目标节点 ID
        relation (str): 链路类型，取值 Link_BKH / Link_A2G / Link_A2A / DISCONN
        snr (float): 链路信噪比 (dB)
        bandwidth (float): 链路带宽 (Mbps)
    """

    pass


class KnowledgeGraph(dict[str, list]):
    """UAV 通信网络图谱 JSON 文件的整体结构

    期望字段:
        nodes (list[NodesData]): 节点列表
        edges (list[EdgesData]): 边列表
        meta (dict): 元数据 (如 field 字段)
    """

    pass


# --- 常量定义 ---
VALID_NODE_TYPES = {"GND-C", "BS", "UAV-R", "UAV-M", "GND-P", "UAV-S"}
VALID_EDGE_RELATIONS = {"Link_BKH", "Link_A2G", "Link_A2A", "Link_G2G", "DISCONN"}


# --- 数据加载器 ---


def load_uav_network_graph(file_path: str) -> KnowledgeGraph:
    """
    从 JSON 文件加载低空无人机通信网络图谱数据。

    Args:
        file_path (str): 图谱 JSON 文件路径
            (通常为 data/mock_uav_network.json)。

    Returns:
        KnowledgeGraph: 加载后的数据，包含 nodes, edges, meta 三个键。

    Raises:
        FileNotFoundError: 文件不存在时抛出。
        ValueError: 数据格式校验失败时抛出。
    """
    print(f"--- 正在从 {file_path} 加载 UAV 通信网络图谱 ---")
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    # 基础结构校验
    if "nodes" not in data or "edges" not in data:
        raise ValueError(
            f"数据格式错误: JSON 文件必须包含 'nodes' 和 'edges' 键，"
            f"实际键: {list(data.keys())}"
        )

    nodes = data["nodes"]
    edges = data["edges"]

    # 节点类型校验
    node_types_found = {n.get("type") for n in nodes}
    invalid_types = node_types_found - VALID_NODE_TYPES
    if invalid_types:
        print(
            f"  ⚠ 警告: 发现未知节点类型 {invalid_types}，有效类型为 {VALID_NODE_TYPES}"
        )

    # 边关系类型校验
    edge_relations_found = {e.get("relation") for e in edges}
    invalid_relations = edge_relations_found - VALID_EDGE_RELATIONS
    if invalid_relations:
        print(
            f"  ⚠ 警告: 发现未知边类型 {invalid_relations}，"
            f"有效类型为 {VALID_EDGE_RELATIONS}"
        )

    # 统计摘要
    type_counts = {}
    for n in nodes:
        ntype = n.get("type", "UNKNOWN")
        type_counts[ntype] = type_counts.get(ntype, 0) + 1

    rel_counts = {}
    for e in edges:
        rel = e.get("relation", "UNKNOWN")
        rel_counts[rel] = rel_counts.get(rel, 0) + 1

    print(f"  ✅ 节点总数: {len(nodes)}, 边总数: {len(edges)}")
    print(f"  📊 节点类型分布: {type_counts}")
    print(f"  📊 边关系分布: {rel_counts}")

    return data
