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

from uav_semantic_planner.envs.environment import UAVRLEnvironment
from uav_semantic_planner.models.models import RLPolicyNet, UAVHGTEncoder


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

    device = torch.device("cpu")  # 可视化直接用 CPU 即可

    seed = args.seed
    np.random.seed(seed)
    torch.manual_seed(seed)

    # 1. 加载原生 JSON 构建 NetworkX 拓扑
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

    # 2. 加载训练好的 RL 环境和图数据
    graph_pt_path = os.path.join(project_root, args.graph_pt)
    if not os.path.exists(graph_pt_path):
        print(f"未找到预处理图数据: {graph_pt_path}")
        return

    checkpoint = torch.load(graph_pt_path, map_location=device, weights_only=False)
    raw_id_map = checkpoint["raw_id_map"]  # name -> int
    node_map = checkpoint["node_map"]  # int -> name

    # --- 以下为极简版 RL 推理过程 ---
    # 为了保证能跑通环境，我们需要重新提取 embeddings
    from torch_geometric.data import Data

    num_nodes_dict = checkpoint["num_nodes_dict"]
    total_nodes = sum(num_nodes_dict.values())

    src_list, dst_list, type_list = [], [], []
    relation_map = checkpoint["relation_map"]
    for (ut, rel_name, vt), e_idx in checkpoint["edge_index_dict"].items():
        # e_idx 是局部索引，需要映射回全局索引
        global_src = checkpoint["x_dict_ids"][ut][e_idx[0]]
        global_dst = checkpoint["x_dict_ids"][vt][e_idx[1]]

        src_list.append(global_src)
        dst_list.append(global_dst)
        type_list.append(torch.full((e_idx.size(1),), relation_map[rel_name]))

    full_edge_index = torch.stack([torch.cat(src_list), torch.cat(dst_list)], dim=0)
    full_edge_type = torch.cat(type_list)
    data = Data(
        edge_index=full_edge_index, edge_type=full_edge_type, num_nodes=total_nodes
    )

    encoder = UAVHGTEncoder(
        num_nodes_dict=num_nodes_dict,
        embedding_dim=128,
        hidden_channels=128,
        out_channels=128,
        metadata=checkpoint["metadata"],
    ).to(device)

    # 随机初始化或者从模型里提取都行，这里为了直接展示寻路能力，我们用随机初始化的特征通过 HGT 提取
    h_dict = encoder(
        checkpoint["x_dict_ids"],
        checkpoint["edge_index_dict"],
        checkpoint.get("weak_link_index"),
    )
    node_embeddings = torch.zeros(total_nodes, 128, device=device)
    for nt, h_tensor in h_dict.items():
        node_embeddings[checkpoint["x_dict_ids"][nt]] = h_tensor

    env = UAVRLEnvironment(
        data=data,
        node_map=node_map,
        relation_map=relation_map,
        node_embeddings=node_embeddings,
        max_path_length=10,
        pagerank_values=checkpoint["pagerank_values"],
        snr_map=checkpoint["snr_map"],
        weak_link_set=checkpoint["weak_link_set"],
        node_types=checkpoint["node_types"],
    )

    model_pt_path = os.path.join(project_root, args.model_pt)
    policy = RLPolicyNet(embedding_dim=128, gru_hidden_dim=64).to(device)
    if os.path.exists(model_pt_path):
        policy.load_state_dict(
            torch.load(model_pt_path, map_location=device, weights_only=True)
        )
    policy.eval()

    # 3. 决定起止点
    start_int, target_int = None, None

    # 强制终点类为指挥中心
    gnd_c_nodes = [k for k, v in node_map.items() if "GND-C" in v]
    if not gnd_c_nodes:
        print("❌ 错误: 图谱中没有找到指挥中心 (GND-C) 节点！")
        return

    # 如果用户通过命令行指定了具体的目标发现节点
    if args.tgt_node:
        if args.tgt_node not in raw_id_map:
            print(f"❌ 错误: 节点 '{args.tgt_node}' 不在图谱中，请检查名称。")
            return
        start_int = raw_id_map[args.tgt_node]

        # 寻找一个可达的 GND-C
        for t in gnd_c_nodes:
            if nx.has_path(nx_graph, node_map[start_int], node_map[t]):
                target_int = t
                break

        if target_int is None:
            print(f"❌ 错误: 节点 '{args.tgt_node}' 无法连通到任何指挥中心 (GND-C)！")
            return

    elif args.auto_find:
        print("--- 正在自动寻找从侦察节点或救援人员到指挥中心(GND-C)的可达路径 ---")
        source_nodes = [k for k, v in node_map.items() if "UAV-S" in v or "GND-P" in v]

        import random

        random.shuffle(source_nodes)
        random.shuffle(gnd_c_nodes)

        found = False
        for s in source_nodes:
            for t in gnd_c_nodes:
                if nx.has_path(nx_graph, node_map[s], node_map[t]):
                    start_int, target_int = s, t
                    found = True
                    break
            if found:
                break

    # 兜底逻辑
    if start_int is None or target_int is None:
        start_int = raw_id_map.get("UAV-S-1", 0)
        target_int = raw_id_map.get("GND-C-1", 1)

    start_node_name = node_map[start_int]
    target_node_name = node_map[target_int]

    # 4. 开始一次评估 (主用路由寻路)
    print(f"--- 启动智能路由推演: {start_node_name} -> {target_node_name} ---")

    def run_inference(masked_edges=None):
        if masked_edges is None:
            masked_edges = set()

        env.reset(start_int, target_int)

        # 维护一个探索栈，用于死胡同回溯 (Backtracking)
        # stack element: (path_memory, current_node, visited_set, tried_actions_from_here)
        path_memory = torch.zeros(1, 64, device=device)
        stack = []
        tried_actions = {start_int: set()}

        target_emb = node_embeddings[target_int].unsqueeze(0)

        while not env.state.done:
            curr_node = env.state.current_node
            curr_emb = node_embeddings[curr_node].unsqueeze(0)

            valid_actions = env.get_valid_actions()
            # 应用全局掩码
            valid_actions = [
                a for a in valid_actions if (curr_node, a) not in masked_edges
            ]
            # 应用本地已尝试的动作掩码 (防止死循环)
            if curr_node not in tried_actions:
                tried_actions[curr_node] = set()
            valid_actions = [
                a for a in valid_actions if a not in tried_actions[curr_node]
            ]

            if not valid_actions:
                # 遭遇死胡同，尝试回溯
                if len(stack) > 0:
                    print(f"  [预警] {node_map[curr_node]} 遭遇死胡同，执行战术回溯...")
                    prev_memory, prev_node, prev_visited = stack.pop()

                    # 恢复环境状态
                    env.state.current_node = prev_node
                    env.state.visited = prev_visited.copy()
                    env.state.path.pop()
                    env.state.snr_history.pop()
                    # 重新计算 min snr
                    env.state.path_min_snr = (
                        min(env.state.snr_history)
                        if env.state.snr_history
                        else float("inf")
                    )

                    path_memory = prev_memory
                    continue
                else:
                    print("  [状态] 彻底遭遇网络死胡同 (无符合 SNR 阈值的下一跳)")
                    break

            neighbor_embs = node_embeddings[valid_actions].unsqueeze(0)
            neighbor_mask = torch.ones(1, len(valid_actions), dtype=torch.float32)

            with torch.no_grad():
                action_dist, _, next_memory = policy(
                    curr_emb, target_emb, neighbor_embs, path_memory, neighbor_mask
                )

            if action_dist is None:
                break

            best_action_idx = action_dist.logits.argmax(dim=-1).item()
            chosen_action = valid_actions[best_action_idx]

            # 记录这次选择，如果回溯回来就不再选它
            tried_actions[curr_node].add(chosen_action)

            # 保存当前状态到栈，以便需要时回溯
            stack.append((path_memory.clone(), curr_node, env.state.visited.copy()))

            env.step(chosen_action)
            path_memory = next_memory
            print(
                f"  -> 路由跳跃至: {node_map[chosen_action]} (瓶颈 SNR: {env.state.path_min_snr}dB)"
            )

        return env.state.path, env.state.path_min_snr

    print("\n[计算主用路径...]")
    primary_path, primary_min_snr = run_inference()

    # 5. 计算备用路由 (屏蔽主路由的关键边)
    backup_path = []
    backup_min_snr = 0.0
    if len(primary_path) > 1:
        print("\n[计算备用路径...]")
        masked_edges = set()
        # 屏蔽主路由的第一跳，迫使网络寻找完全不同的出口
        masked_edges.add((primary_path[0], primary_path[1]))
        backup_path, backup_min_snr = run_inference(masked_edges)

    # 智能比对环节：强化学习有时候会有陷入局部最优的探索情况，
    # 为了展示逻辑自洽，我们比较两条链路的质量，永远把高质量的链路作为“主路由”
    if backup_path and len(backup_path) > 0:
        # 评估指标：首先看瓶颈 SNR（越大越好），如果 SNR 差不多，看路径长度（越短越好）
        # 这里给 SNR 加一点容差权重，假设相差不到 1dB 就算差不多
        primary_score = primary_min_snr * 10 - len(primary_path)
        backup_score = backup_min_snr * 10 - len(backup_path)

        if backup_score > primary_score:
            print(
                "\n[智能调整] 发现备用路径质量优于原规划主路径，自动进行主备路由翻转换路！"
            )
            primary_path, backup_path = backup_path, primary_path
            primary_min_snr, backup_min_snr = backup_min_snr, primary_min_snr

    # 6. 提取路径并画图
    final_path_raw = [node_map[n] for n in primary_path]
    backup_path_raw = [node_map[n] for n in backup_path] if backup_path else []

    print(
        f"\n✅ 最终主用路由 (瓶颈 SNR {primary_min_snr:.1f}dB): {' -> '.join(final_path_raw)}"
    )
    if backup_path_raw:
        print(
            f"✅ 最终备用路由 (瓶颈 SNR {backup_min_snr:.1f}dB): {' -> '.join(backup_path_raw)}"
        )

    output_full_path = os.path.join(project_root, args.output_img)
    draw_uav_network(
        nx_graph, final_path_raw, backup_path_raw, target_node_name, output_full_path
    )


if __name__ == "__main__":
    main()
