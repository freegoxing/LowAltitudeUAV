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
matplotlib.use("Agg")  # 强制使用无头模式
import matplotlib.pyplot as plt
import networkx as nx
import torch

# 自动处理路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from uav_semantic_planner.envs.environment import UAVRLEnvironment
from uav_semantic_planner.models.models import UAVHGTEncoder, RLPolicyNet


def draw_uav_network(
    nx_graph: nx.Graph,
    path_nodes: list[str],
    output_path: str,
    title: str = "UAV Semantic Communication Resource Routing",
):
    """使用 NetworkX 绘制层次化的 UAV 通信拓扑，并高亮资源流向路径"""
    plt.figure(figsize=(16, 10))

    # 1. 确定多层（层次化）布局
    # GND-C(0) -> BS(1) -> UAV-R(2) -> UAV-M(3) -> GND-P(4)
    layer_map = {"GND-C": 0, "BS": 1, "UAV-R": 2, "UAV-M": 3, "GND-P": 4}
    for node, data in nx_graph.nodes(data=True):
        ntype = data.get("type", "GND-P")
        nx_graph.nodes[node]["layer"] = layer_map.get(ntype, 4)

    pos = nx.multipartite_layout(nx_graph, subset_key="layer", align="horizontal")

    # 2. 区分节点类型进行绘制
    type_colors = {
        "GND-C": "#FF6B6B",  # 红色: 指挥车
        "BS": "#4ECDC4",     # 青色: 基站
        "UAV-R": "#45B7D1",  # 蓝色: 中继
        "UAV-M": "#96CEB4",  # 绿色: 任务机
        "GND-P": "#FFEEAD",  # 黄色: 地面人员
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

    # 3. 区分边类型进行绘制
    # 正常边 (灰色虚线)，DISCONN断连预警 (红色点线)
    normal_edges = [(u, v) for u, v, d in nx_graph.edges(data=True) if d.get("relation") != "DISCONN"]
    disconn_edges = [(u, v) for u, v, d in nx_graph.edges(data=True) if d.get("relation") == "DISCONN"]

    nx.draw_networkx_edges(
        nx_graph, pos, edgelist=normal_edges, edge_color="#B0B0B0", style="dashed", alpha=0.5
    )
    nx.draw_networkx_edges(
        nx_graph, pos, edgelist=disconn_edges, edge_color="#FF9999", style="dotted", width=2.0, alpha=0.7
    )

    # 4. 高亮 RL 规划出的资源路由路径 (加粗红色箭头)
    path_edges = []
    if path_nodes and len(path_nodes) > 1:
        for i in range(len(path_nodes) - 1):
            path_edges.append((path_nodes[i], path_nodes[i + 1]))

        # 使用有向箭头高亮路径
        nx.draw_networkx_edges(
            nx_graph,
            pos,
            edgelist=path_edges,
            edge_color="#FF3366",
            width=3.5,
            arrows=True,
            arrowsize=25,
            arrowstyle="-|>",
            connectionstyle="arc3,rad=0.1" # 轻微弯曲以避开双向边重叠
        )

    # 5. 绘制标签
    nx.draw_networkx_labels(nx_graph, pos, font_size=9, font_weight="bold")

    # 给路径边加上 SNR 数值标签
    edge_labels = {}
    for u, v in path_edges:
        if nx_graph.has_edge(u, v):
            snr = nx_graph[u][v].get("snr", 0.0)
            edge_labels[(u, v)] = f"{snr}dB"
    
    nx.draw_networkx_edge_labels(
        nx_graph, pos, edge_labels=edge_labels, font_color="red", font_size=10, font_weight="bold"
    )

    # 6. 图例与标题
    plt.legend(scatterpoints=1, frameon=True, loc="upper right", title="Node Types")
    plt.title(title, fontsize=16, fontweight="bold", pad=20)
    plt.axis("off")
    plt.tight_layout()

    # 保存
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"✅ 路由可视化图像已生成: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Visualize UAV RL Routing")
    parser.add_argument("--json_path", type=str, default="data/mock_uav_network.json")
    parser.add_argument("--graph_pt", type=str, default="checkpoints/UAV_Demo/uav_hetero_graph.pt")
    parser.add_argument("--model_pt", type=str, default="checkpoints/UAV_Demo/uav_policy_final.pt")
    parser.add_argument("--output_img", type=str, default="checkpoints/UAV_Demo/routing_visualization.png")
    parser.add_argument("--start_node", type=str, default="GND-C-1")
    parser.add_argument("--target_node", type=str, default="GND-P-1")
    args = parser.parse_args()

    device = torch.device("cpu") # 可视化直接用 CPU 即可
    
    # 1. 加载原生 JSON 构建 NetworkX 拓扑
    json_full_path = os.path.join(project_root, args.json_path)
    with open(json_full_path, "r", encoding="utf-8") as f:
        kg_data = json.load(f)
        
    nx_graph = nx.DiGraph()
    for n in kg_data["nodes"]:
        nx_graph.add_node(n["id"], type=n["type"])
    for e in kg_data["edges"]:
        nx_graph.add_edge(e["source"], e["target"], relation=e["relation"], snr=e["snr"])

    # 2. 加载训练好的 RL 环境和图数据
    graph_pt_path = os.path.join(project_root, args.graph_pt)
    if not os.path.exists(graph_pt_path):
        print(f"未找到预处理图数据: {graph_pt_path}")
        return

    checkpoint = torch.load(graph_pt_path, map_location=device, weights_only=False)
    raw_id_map = checkpoint["raw_id_map"] # name -> int
    node_map = checkpoint["node_map"]     # int -> name
    
    if args.start_node not in raw_id_map or args.target_node not in raw_id_map:
        print(f"节点 {args.start_node} 或 {args.target_node} 不在图谱中，请检查名称。")
        return

    start_int = raw_id_map[args.start_node]
    target_int = raw_id_map[args.target_node]

    # --- 以下为极简版 RL 推理过程 ---
    # 为了保证能跑通环境，我们需要重新提取 embeddings
    from torch_geometric.data import Data
    num_nodes_dict = checkpoint["num_nodes_dict"]
    total_nodes = sum(num_nodes_dict.values())
    
    src_list, dst_list, type_list = [], [], []
    relation_map = checkpoint["relation_map"]
    for (ut, rel_name, vt), e_idx in checkpoint["edge_index_dict"].items():
        src_list.append(e_idx[0])
        dst_list.append(e_idx[1])
        type_list.append(torch.full((e_idx.size(1),), relation_map[rel_name]))
    
    full_edge_index = torch.stack([torch.cat(src_list), torch.cat(dst_list)], dim=0)
    full_edge_type = torch.cat(type_list)
    data = Data(edge_index=full_edge_index, edge_type=full_edge_type, num_nodes=total_nodes)

    encoder = UAVHGTEncoder(
        num_nodes_dict=num_nodes_dict,
        embedding_dim=128,
        hidden_channels=128,
        out_channels=128,
        metadata=checkpoint["metadata"],
    ).to(device)

    # 随机初始化或者从模型里提取都行，这里为了直接展示寻路能力，我们用随机初始化的特征通过 HGT 提取
    h_dict = encoder(checkpoint["x_dict_ids"], checkpoint["edge_index_dict"], checkpoint.get("weak_link_index"))
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
        policy.load_state_dict(torch.load(model_pt_path, map_location=device, weights_only=True))
    policy.eval()

    # 3. 开始一次评估 (寻路)
    print(f"--- 启动智能路由推演: {args.start_node} -> {args.target_node} ---")
    env.reset(start_int, target_int)
    path_memory = torch.zeros(1, 64, device=device)
    target_emb = node_embeddings[target_int].unsqueeze(0)

    while not env.state.done:
        curr_node = env.state.current_node
        curr_emb = node_embeddings[curr_node].unsqueeze(0)
        
        valid_actions = env.get_valid_actions()
        if not valid_actions:
            print("  [状态] 遭遇网络死胡同 (无符合 SNR 阈值的下一跳)")
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
        
        # 为了演示，如果遇到循环则强行打断
        if chosen_action in env.state.path:
            print(f"  [预警] 检测到路由环路，已终止于 {node_map[curr_node]}")
            break
            
        env.step(chosen_action)
        path_memory = next_memory
        print(f"  -> 路由跳跃至: {node_map[chosen_action]} (瓶颈 SNR: {env.state.path_min_snr}dB)")

    # 4. 提取路径并画图
    final_path_raw = [node_map[n] for n in env.state.path]
    print(f"\n✅ 最终决策路由: {' -> '.join(final_path_raw)}")

    output_full_path = os.path.join(project_root, args.output_img)
    draw_uav_network(nx_graph, final_path_raw, output_full_path)


if __name__ == "__main__":
    main()
