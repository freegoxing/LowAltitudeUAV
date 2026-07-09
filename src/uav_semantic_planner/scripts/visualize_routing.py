"""
UAV 语义通信网络资源路由可视化脚本

基于训练好的强化学习 (RL) 策略，在通信网络拓扑中进行寻路，
并将通信资源的流向（网络拓扑、SNR态势、最终决策路由）进行可视化图表输出。
"""

import argparse
import json
import os
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")  # 强制使用无头模式
import matplotlib.pyplot as plt
import networkx as nx
import torch

# 自动处理路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from uav_semantic_planner.utils import UAVRoutingPlanner


def draw_uav_network(
    nx_graph: nx.Graph,
    path_nodes: list[str],
    backup_path_nodes: list[str],
    target_node_name: str,
    output_path: str,
    title: str = "UAV Semantic Communication Resource Routing",
):
    """使用 NetworkX 绘制层次化的 UAV 通信拓扑，并高亮资源流向路径"""
    plt.figure(figsize=(16, 10))

    # 1. 确定多层（层次化）布局
    layer_map = {"GND-C": 0, "BS": 1, "UAV-R": 2, "UAV-M": 3, "UAV-S": 4, "GND-P": 5}
    layer_nodes = {0: [], 1: [], 2: [], 3: [], 4: [], 5: []}

    for node, data in nx_graph.nodes(data=True):
        ntype = data.get("type", "GND-P")
        layer_idx = layer_map.get(ntype, 5)
        nx_graph.nodes[node]["layer"] = layer_idx
        layer_nodes[layer_idx].append(node)

    for idx in layer_nodes:
        layer_nodes[idx].sort()

    pos = nx.multipartite_layout(nx_graph, subset_key=layer_nodes, align="horizontal")
    # 2. 区分节点类型进行绘制
    type_colors = {
        "GND-C": "#FF6B6B",
        "BS": "#4ECDC4",
        "UAV-R": "#45B7D1",
        "UAV-M": "#96CEB4",
        "GND-P": "#FFEEAD",
        "UAV-S": "#B19CD9",
    }

    for ntype, color in type_colors.items():
        nlist = [n for n, d in nx_graph.nodes(data=True) if d.get("type") == ntype]
        if nlist:
            nx.draw_networkx_nodes(
                nx_graph,
                pos,
                nodelist=nlist,
                node_color=color,
                node_size=800,
                edgecolors="black",
                linewidths=1.5,
                label=ntype,
            )

    # 特别高亮起点和终点 (Target)
    if path_nodes:
        start_node = path_nodes[0]
        # 起点 (绿色边框加粗)
        nx.draw_networkx_nodes(
            nx_graph,
            pos,
            nodelist=[start_node],
            node_size=1200,
            edgecolors="#32CD32",
            linewidths=4.0,
        )

    # 目标点 (紫色边框加粗，并且特别标注)
    if nx_graph.has_node(target_node_name):
        nx.draw_networkx_nodes(
            nx_graph,
            pos,
            nodelist=[target_node_name],
            node_size=1200,
            edgecolors="#9932CC",
            linewidths=4.0,
        )
        # 为目标点画一个五角星标记
        nx.draw_networkx_nodes(
            nx_graph,
            pos,
            nodelist=[target_node_name],
            node_shape="*",
            node_size=2500,
            edgecolors="#9932CC",
            node_color="none",
        )

    # 3. 区分边类型进行绘制
    normal_edges = [
        (u, v)
        for u, v, d in nx_graph.edges(data=True)
        if d.get("relation") != "DISCONN"
    ]
    disconn_edges = [
        (u, v)
        for u, v, d in nx_graph.edges(data=True)
        if d.get("relation") == "DISCONN"
    ]

    nx.draw_networkx_edges(
        nx_graph,
        pos,
        edgelist=normal_edges,
        edge_color="#B0B0B0",
        style="dashed",
        alpha=0.5,
    )
    nx.draw_networkx_edges(
        nx_graph,
        pos,
        edgelist=disconn_edges,
        edge_color="#FF9999",
        style="dotted",
        width=2.0,
        alpha=0.7,
    )

    # 4. 高亮 RL 规划出的 备用 资源路由路径 (加粗橙色虚线箭头)
    backup_path_edges = []
    if backup_path_nodes and len(backup_path_nodes) > 1:
        for i in range(len(backup_path_nodes) - 1):
            backup_path_edges.append((backup_path_nodes[i], backup_path_nodes[i + 1]))

        nx.draw_networkx_edges(
            nx_graph,
            pos,
            edgelist=backup_path_edges,
            edge_color="#FF9900",
            width=2.5,
            style="dashed",
            arrows=True,
            arrowsize=20,
            arrowstyle="-|>",
            connectionstyle="arc3,rad=-0.15",  # 反向弯曲，避免重叠
        )

    # 5. 高亮 RL 规划出的 主用 资源路由路径 (加粗红色实线箭头)
    path_edges = []
    if path_nodes and len(path_nodes) > 1:
        for i in range(len(path_nodes) - 1):
            path_edges.append((path_nodes[i], path_nodes[i + 1]))

        nx.draw_networkx_edges(
            nx_graph,
            pos,
            edgelist=path_edges,
            edge_color="#FF3366",
            width=3.5,
            arrows=True,
            arrowsize=25,
            arrowstyle="-|>",
            connectionstyle="arc3,rad=0.1",
        )

    # 6. 绘制标签
    nx.draw_networkx_labels(nx_graph, pos, font_size=9, font_weight="bold")

    edge_labels = {}
    for u, v in path_edges:
        if nx_graph.has_edge(u, v):
            snr = nx_graph[u][v].get("snr", 0.0)
            edge_labels[(u, v)] = f"{snr}dB"
    for u, v in backup_path_edges:
        if nx_graph.has_edge(u, v) and (u, v) not in edge_labels:
            snr = nx_graph[u][v].get("snr", 0.0)
            edge_labels[(u, v)] = f"{snr}dB (Backup)"

    nx.draw_networkx_edge_labels(
        nx_graph,
        pos,
        edge_labels=edge_labels,
        font_color="black",
        font_size=8,
        font_weight="bold",
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.7),
    )

    # 7. 图例与标题
    import matplotlib.lines as mlines

    legend_handles = []
    for ntype, color in type_colors.items():
        handle = mlines.Line2D(
            [],
            [],
            color="w",
            marker="o",
            markerfacecolor=color,
            markeredgecolor="black",
            markersize=10,
            label=f"Node: {ntype}",
        )
        legend_handles.append(handle)

    legend_handles.append(
        mlines.Line2D(
            [],
            [],
            color="w",
            marker="*",
            markerfacecolor="none",
            markeredgecolor="#9932CC",
            markersize=15,
            markeredgewidth=2,
            label="Target Destination",
        )
    )

    legend_handles.append(
        mlines.Line2D(
            [],
            [],
            color="#B0B0B0",
            linestyle="dashed",
            linewidth=1.5,
            label="Available Link (SNR >= threshold)",
        )
    )
    legend_handles.append(
        mlines.Line2D(
            [],
            [],
            color="#FF9999",
            linestyle="dotted",
            linewidth=2.0,
            label="DISCONN Warning (Weak/Broken)",
        )
    )
    legend_handles.append(
        mlines.Line2D(
            [],
            [],
            color="#FF3366",
            linestyle="-",
            linewidth=3.5,
            label="Primary Routing Path",
        )
    )
    legend_handles.append(
        mlines.Line2D(
            [],
            [],
            color="#FF9900",
            linestyle="dashed",
            linewidth=2.5,
            label="Backup Routing Path",
        )
    )

    plt.legend(
        handles=legend_handles,
        frameon=True,
        loc="upper right",
        title="Network Elements Legend",
        fontsize=9,
    )
    plt.title(title, fontsize=16, fontweight="bold", pad=20)

    info_text = f"Start Node: {path_nodes[0] if path_nodes else 'N/A'}\nTarget Node: {target_node_name}"
    plt.text(
        0.02,
        0.98,
        info_text,
        transform=plt.gca().transAxes,
        fontsize=12,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    plt.axis("off")
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"✅ 路由可视化图像已生成: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Visualize UAV RL Routing")
    parser.add_argument("--json_path", type=str, default="data/mock_uav_network.json")
    parser.add_argument(
        "--graph_pt", type=str, default="checkpoints/UAV_Demo/uav_hetero_graph.pt"
    )
    parser.add_argument(
        "--model_pt", type=str, default="checkpoints/UAV_Demo/uav_policy_final.pt"
    )
    parser.add_argument(
        "--output_img", type=str, default="visualizations/routing_flow.png"
    )
    # 增加指定起点（即发现目标的节点）的参数，终点强制为 GND-C
    parser.add_argument(
        "--tgt_node",
        type=str,
        default="",
        help="指定发现目标的节点名称(如 UAV-S-1)，数据将自动回传至指挥中心",
    )
    # 全局随机种子
    parser.add_argument("--seed", type=int, default=4321, help="全局随机种子")
    # 自动寻路开关 (如果指定了起点终点，请将此参数设为 False)
    parser.add_argument(
        "--auto_find", action="store_true", help="是否在未指定节点时自动寻找连通节点"
    )
    args = parser.parse_args()

    # 1. 设置随机种子
    seed = args.seed
    np.random.seed(seed)
    torch.manual_seed(seed)

    # 2. 加载原生 JSON 构建 NetworkX 拓扑
    json_full_path = os.path.join(project_root, args.json_path)
    with open(json_full_path, encoding="utf-8") as f:
        kg_data = json.load(f)

    nx_graph = nx.DiGraph()
    for n in kg_data["nodes"]:
        nx_graph.add_node(n["id"], type=n["type"])
    for e in kg_data["edges"]:
        nx_graph.add_edge(
            e["source"], e["target"], relation=e["relation"], snr=e["snr"]
        )

    # 3. 初始化路由规划器
    model_pt_path = os.path.join(project_root, args.model_pt)
    graph_pt_path = os.path.join(project_root, args.graph_pt)

    try:
        planner = UAVRoutingPlanner(
            model_pt_path=model_pt_path,
            graph_pt_path=graph_pt_path,
            device="cpu"
        )
    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
        return

    # 4. 决定起止点
    try:
        start_node_name, target_node_name = planner.select_routing_endpoints(
            nx_graph=nx_graph,
            tgt_node=args.tgt_node,
            auto_find=args.auto_find
        )
    except ValueError as e:
        print(f"❌ 错误: {e}")
        return

    # 5. 开始智能路由规划
    print(f"--- 启动智能路由推演: {start_node_name} -> {target_node_name} ---")
    routing_result = planner.plan_routing(start_node_name, target_node_name)

    primary_path = routing_result["primary_path"]
    primary_min_snr = routing_result["primary_min_snr"]
    backup_path = routing_result["backup_path"]
    backup_min_snr = routing_result["backup_min_snr"]

    print(
        f"\n✅ 最终主用路由 (瓶颈 SNR {primary_min_snr:.1f}dB): {' -> '.join(primary_path)}"
    )
    if backup_path:
        print(
            f"✅ 最终备用路由 (瓶颈 SNR {backup_min_snr:.1f}dB): {' -> '.join(backup_path)}"
        )

    output_full_path = os.path.join(project_root, args.output_img)
    draw_uav_network(
        nx_graph, primary_path, backup_path, target_node_name, output_full_path
    )


if __name__ == "__main__":
    main()
