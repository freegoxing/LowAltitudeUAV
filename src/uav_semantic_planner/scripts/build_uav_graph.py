"""
UAV 语义通信网络图谱预处理与异构图构建脚本
(替代原 MOOCCubeX 的图构建脚本)
"""

import argparse
import os
import sys

# 自动处理路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import torch

from uav_semantic_planner.data.data_loader import load_uav_network_graph
from uav_semantic_planner.utils.data_processing import (
    convert_to_hetero,
    process_uav_graph,
)


def main():
    parser = argparse.ArgumentParser(description="UAV 通信网络异构图离线构建工具")
    parser.add_argument(
        "--input_file",
        type=str,
        default="data/mock_uav_network.json",
        help="原始数据 JSON",
    )
    parser.add_argument(
        "--output_dir", type=str, default="checkpoints/UAV_Demo", help="输出目录"
    )
    parser.add_argument(
        "--snr_threshold", type=float, default=5.0, help="标记为弱链路的 SNR 阈值 (dB)"
    )
    args = parser.parse_args()

    input_path = os.path.join(project_root, args.input_file)
    output_dir = os.path.join(project_root, args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    print("=== 启动离线图构建 ===")

    # 1. 加载 JSON 数据
    kg_data = load_uav_network_graph(input_path)

    # 2. 处理为 PyG Data 并提取特征
    (
        data,
        node_map,
        relation_map,
        pagerank_values,
        node_types,
        snr_map,
        weak_link_set,
        int_id_to_raw_id,
    ) = process_uav_graph(kg_data, snr_threshold=args.snr_threshold)

    # 3. 转换为异构图格式 (HGT 格式)
    x_dict_ids, edge_index_dict, metadata = convert_to_hetero(
        data, node_types, data.edge_type, relation_map
    )

    # 提取弱链路索引张量 (Weak Link Index) 用于 HGT 惩罚注入
    weak_src = []
    weak_dst = []
    for s, t in weak_link_set:
        weak_src.append(s)
        weak_dst.append(t)

    weak_link_index = None
    if weak_src:
        weak_link_index = torch.tensor([weak_src, weak_dst], dtype=torch.long)

    # 4. 保存为统一的 .pt 格式，供训练脚本直接加载
    save_path = os.path.join(output_dir, "uav_hetero_graph.pt")

    checkpoint_data = {
        "x_dict_ids": x_dict_ids,
        "edge_index_dict": edge_index_dict,
        "metadata": metadata,
        "weak_link_index": weak_link_index,
        "node_map": node_map,  # int_id -> name
        "relation_map": relation_map,  # rel_name -> int_id
        "pagerank_values": pagerank_values,
        "node_types": node_types,
        "snr_map": snr_map,
        "weak_link_set": weak_link_set,
        "raw_id_map": {v: k for k, v in int_id_to_raw_id.items()},  # name -> int_id
        "num_nodes_dict": {nt: len(indices) for nt, indices in x_dict_ids.items()},
    }

    torch.save(checkpoint_data, save_path)

    print(f"=== 构建完成！缓存已保存至: {save_path} ===")
    print(f"--- 节点总数: {data.num_nodes}")
    print(f"--- 边总数: {data.num_edges}")
    print(f"--- 弱链路/预警断连数: {len(weak_link_set)}")
    print(f"--- 异构类型数: {len(x_dict_ids)}")


if __name__ == "__main__":
    main()
