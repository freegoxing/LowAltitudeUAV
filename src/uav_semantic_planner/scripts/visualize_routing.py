"""
UAV 语义通信任务子图可视化脚本

基于训练好的强化学习 (RL) 策略，在通信网络拓扑中规划任务通信子图，
并将关键节点、主备路径、资源约束与自愈信息进行可视化输出。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

import matplotlib
import networkx as nx
import numpy as np
import torch
from matplotlib import font_manager

matplotlib.use("Agg")
import matplotlib.lines as mlines
import matplotlib.pyplot as plt

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from uav_semantic_planner.utils import (
    MissionCommunicationSpecification,
    MissionFlowSpec,
    UAVRoutingPlanner,
)


def _configure_chinese_font() -> None:
    """优先选择可用的中文字体，避免导出图片出现方块字。"""
    preferred_fonts = [
        "Noto Sans CJK SC",
        "Microsoft YaHei",
        "SimHei",
        "WenQuanYi Zen Hei",
        "Arial Unicode MS",
    ]
    available_fonts = {f.name for f in font_manager.fontManager.ttflist}
    for font_name in preferred_fonts:
        if font_name in available_fonts:
            matplotlib.rcParams["font.sans-serif"] = [font_name]
            break
    matplotlib.rcParams["axes.unicode_minus"] = False


_configure_chinese_font()


def build_default_mission_spec(
    source_node: str,
    search_receiver: str,
    medical_receiver: str,
    command_receiver: str,
) -> MissionCommunicationSpecification:
    """生成一个与设计文档一致的默认火灾搜救 MCS 示例。"""
    return MissionCommunicationSpecification(
        mission_id="SAR-FIRE-001",
        mission_type="TASK-SAR",
        mission_priority=5,
        key_nodes=[
            source_node,
            search_receiver,
            medical_receiver,
            command_receiver,
        ],
        mission_flows=[
            MissionFlowSpec(
                flow_id="F-1",
                source=source_node,
                receivers=[search_receiver],
                purpose="搜救引导",
                priority=5,
                bandwidth_req="15 Mbps",
                latency_req="120 ms",
                reliability_req=0.99,
                delivery_mode="anycast",
                command_sync="immediate",
            ),
            MissionFlowSpec(
                flow_id="F-2",
                source=source_node,
                receivers=[medical_receiver],
                purpose="医疗协同",
                priority=4,
                bandwidth_req="8 Mbps",
                latency_req="200 ms",
                reliability_req=0.97,
                delivery_mode="unicast",
                command_sync="summary",
            ),
            MissionFlowSpec(
                flow_id="F-3",
                source=search_receiver,
                receivers=[command_receiver],
                purpose="态势同步",
                priority=2,
                bandwidth_req="2 Mbps",
                latency_req="1 s",
                reliability_req=0.9,
                delivery_mode="unicast",
                command_sync="summary",
            ),
        ],
        resource_budget={
            "mission_bandwidth_cap": "70%",
            "relay_count_cap": 3,
            "power_ceiling": "+3 dB",
        },
        backup_requirement={"priority_5": 2, "priority_4": 1},
        healing_policy={
            "switch_threshold_snr_db": 8,
            "switch_delay": "<500 ms",
            "recovery": "automatic",
        },
        command_receiver=command_receiver,
    )


def _format_budget_line(resource_budget: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in resource_budget.items())


def draw_task_communication_subgraph(
    nx_graph: nx.Graph,
    planning_result: dict,
    output_path: str,
    title: str = "Task Communication Subgraph",
) -> None:
    """绘制任务通信子图、主备路径与任务约束摘要。"""
    plt.figure(figsize=(18, 11))

    layer_map = {"GND-C": 0, "BS": 1, "UAV-R": 2, "UAV-M": 3, "UAV-S": 4, "GND-P": 5}
    layer_nodes = defaultdict(list)
    for node, data in nx_graph.nodes(data=True):
        ntype = data.get("type", "GND-P")
        layer_idx = layer_map.get(ntype, 5)
        nx_graph.nodes[node]["layer"] = layer_idx
        layer_nodes[layer_idx].append(node)

    for idx in layer_nodes:
        layer_nodes[idx].sort()

    pos = nx.multipartite_layout(nx_graph, subset_key="layer", align="horizontal")

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
                node_size=780,
                edgecolors="black",
                linewidths=1.2,
                label=ntype,
            )

    mission = planning_result["mission"]
    key_nodes = set(mission.get("key_nodes", []))
    command_receiver = mission.get("command_receiver")

    for node in key_nodes:
        if nx_graph.has_node(node):
            nx.draw_networkx_nodes(
                nx_graph,
                pos,
                nodelist=[node],
                node_size=1200,
                edgecolors="#F5B700",
                linewidths=3.5,
                node_color="none",
            )

    if command_receiver and nx_graph.has_node(command_receiver):
        nx.draw_networkx_nodes(
            nx_graph,
            pos,
            nodelist=[command_receiver],
            node_size=1350,
            edgecolors="#9932CC",
            linewidths=4.0,
            node_color="none",
        )

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
        edge_color="#C8C8C8",
        style="dashed",
        alpha=0.45,
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

    flow_palette = ["#FF3366", "#FF9900", "#6A5ACD", "#1E90FF", "#2E8B57"]
    edge_labels: dict[tuple[str, str], str] = {}
    legend_handles = []

    for idx, flow_result in enumerate(planning_result["flow_results"]):
        flow = flow_result["flow"]
        color = flow_palette[idx % len(flow_palette)]
        primary_path = flow_result["primary_path"]
        backup_paths = flow_result["backup_paths"]

        primary_edges = list(zip(primary_path[:-1], primary_path[1:]))
        if primary_edges:
            nx.draw_networkx_edges(
                nx_graph,
                pos,
                edgelist=primary_edges,
                edge_color=color,
                width=3.5,
                arrows=True,
                arrowsize=22,
                arrowstyle="-|>",
                connectionstyle="arc3,rad=0.1",
            )

        for backup_idx, backup_path in enumerate(backup_paths):
            backup_edges = list(zip(backup_path[:-1], backup_path[1:]))
            if not backup_edges:
                continue
            nx.draw_networkx_edges(
                nx_graph,
                pos,
                edgelist=backup_edges,
                edge_color=color,
                width=2.5,
                style="dashed",
                arrows=True,
                arrowsize=18,
                arrowstyle="-|>",
                alpha=0.8,
                connectionstyle=f"arc3,rad={-0.12 - 0.03 * backup_idx}",
            )

        for u, v in primary_edges:
            if nx_graph.has_edge(u, v):
                edge_labels[(u, v)] = f"{nx_graph[u][v].get('snr', 0.0)}dB"
        for backup_path in backup_paths:
            for u, v in zip(backup_path[:-1], backup_path[1:]):
                if nx_graph.has_edge(u, v) and (u, v) not in edge_labels:
                    edge_labels[(u, v)] = f"{nx_graph[u][v].get('snr', 0.0)}dB*"

        flow_label = (
            f"{flow['flow_id']} | {flow['purpose']} | "
            f"recv: {flow_result['selected_receiver']} | "
            f"P{flow['priority']} | {flow_result['status']}"
        )
        legend_handles.append(
            mlines.Line2D(
                [],
                [],
                color=color,
                linewidth=3,
                label=flow_label,
            )
        )

    nx.draw_networkx_labels(nx_graph, pos, font_size=9, font_weight="bold")
    nx.draw_networkx_edge_labels(
        nx_graph,
        pos,
        edge_labels=edge_labels,
        font_color="black",
        font_size=8,
        font_weight="bold",
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.7),
    )

    legend_handles.extend(
        [
            mlines.Line2D(
                [],
                [],
                color="w",
                marker="o",
                markerfacecolor=color,
                markeredgecolor="black",
                markersize=10,
                label=f"Node: {ntype}",
            )
            for ntype, color in type_colors.items()
        ]
    )
    legend_handles.append(
        mlines.Line2D(
            [],
            [],
            color="w",
            marker="o",
            markerfacecolor="none",
            markeredgecolor="#F5B700",
            markersize=12,
            markeredgewidth=2,
            label="Key Node",
        )
    )
    legend_handles.append(
        mlines.Line2D(
            [],
            [],
            color="w",
            marker="o",
            markerfacecolor="none",
            markeredgecolor="#9932CC",
            markersize=12,
            markeredgewidth=2,
            label="Command Receiver",
        )
    )
    legend_handles.append(
        mlines.Line2D(
            [],
            [],
            color="#C8C8C8",
            linestyle="dashed",
            linewidth=1.5,
            label="Available Link",
        )
    )
    legend_handles.append(
        mlines.Line2D(
            [],
            [],
            color="#FF9999",
            linestyle="dotted",
            linewidth=2.0,
            label="DISCONN Warning",
        )
    )

    plt.legend(
        handles=legend_handles,
        frameon=True,
        loc="upper right",
        title="Task Communication Legend",
        fontsize=9,
    )
    plt.title(title, fontsize=16, fontweight="bold", pad=20)

    flow_summary = []
    for flow_result in planning_result["flow_results"]:
        flow = flow_result["flow"]
        primary_path = flow_result["primary_path"]
        if not primary_path:
            flow_summary.append(
                f"{flow['flow_id']}: {flow['source']} -> "
                f"{flow_result['selected_receiver']} | 不可达"
            )
            continue
        flow_summary.append(
            f"{flow['flow_id']}: {primary_path[0]} -> "
            f"{flow_result['selected_receiver']} | "
            f"主路瓶颈 {flow_result['primary_min_snr']:.1f}dB | "
            f"备份 {len(flow_result['backup_paths'])}"
        )

    info_text = (
        f"Mission: {mission['mission_id']} ({mission['mission_type']})\n"
        f"Priority: {mission['mission_priority']}\n"
        f"Key Nodes: {', '.join(mission.get('key_nodes', []))}\n"
        f"Budget: {_format_budget_line(mission.get('resource_budget', {}))}\n"
        f"Healing: {_format_budget_line(mission.get('healing_policy', {}))}\n"
        f"{' | '.join(flow_summary)}"
    )
    plt.text(
        0.02,
        0.98,
        info_text,
        transform=plt.gca().transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.82),
    )

    plt.axis("off")
    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"✅ 任务通信子图已生成: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize UAV task communication subgraph")
    parser.add_argument("--json_path", type=str, default="data/mock_uav_network.json")
    parser.add_argument(
        "--graph_pt", type=str, default="checkpoints/UAV_Demo/uav_hetero_graph.pt"
    )
    parser.add_argument(
        "--model_pt", type=str, default="checkpoints/UAV_Demo/uav_policy_final.pt"
    )
    parser.add_argument(
        "--output_img", type=str, default="visualizations/task_communication_subgraph.png"
    )
    parser.add_argument("--source_node", type=str, default="UAV-S-1")
    parser.add_argument("--search_receiver", type=str, default="GND-P-1")
    parser.add_argument("--medical_receiver", type=str, default="GND-P-2")
    parser.add_argument("--command_receiver", type=str, default="GND-C-1")
    parser.add_argument("--seed", type=int, default=4321, help="全局随机种子")
    args = parser.parse_args()

    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

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

    model_pt_path = os.path.join(project_root, args.model_pt)
    graph_pt_path = os.path.join(project_root, args.graph_pt)

    try:
        planner = UAVRoutingPlanner(
            model_pt_path=model_pt_path,
            graph_pt_path=graph_pt_path,
            device="cpu",
        )
    except FileNotFoundError as exc:
        print(f"❌ 错误: {exc}")
        return

    mission_spec = build_default_mission_spec(
        source_node=args.source_node,
        search_receiver=args.search_receiver,
        medical_receiver=args.medical_receiver,
        command_receiver=args.command_receiver,
    )

    print(f"--- 启动任务通信子图推演: {mission_spec.mission_id} ---")
    planning_result = planner.plan_mission_communication(mission_spec, nx_graph)
    draw_task_communication_subgraph(
        nx_graph,
        planning_result,
        os.path.join(project_root, args.output_img),
    )


if __name__ == "__main__":
    main()
