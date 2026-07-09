"""
UAV 通信网络 Mock 数据生成器

生成用于 Demo 的轻量级低空无人机通信网络图谱。
层次化拓扑结构: GND-C → BS → UAV-R → UAV-M → GND-P
仅考虑 SNR 状态，不包含三维坐标。
"""

import json
import os
import random


def generate_mock_uav_data(output_file="data/mock_uav_network.json"):
    """
    生成一个用于 Demo 的轻量级低空无人机通信网络图谱。

    节点类型: GND-C, BS, UAV-R, UAV-M, GND-P, UAV-S
    边类型: Link_BKH, Link_A2G, Link_A2A, Link_G2G, DISCONN
    """
    nodes = []
    edges = []

    # --- 1. 节点生成配置 ---
    node_configs = {
        "GND-C": {"count": 2, "desc": "地面指挥车"},
        "BS": {"count": 4, "desc": "基站"},
        "UAV-R": {"count": 8, "desc": "中继无人机"},
        "UAV-M": {"count": 10, "desc": "任务无人机"},
        "GND-P": {"count": 5, "desc": "地面救援人员(终端)"},
        "UAV-S": {"count": 3, "desc": "侦察无人机"},
    }

    # 生成节点
    node_ids_by_type = {ntype: [] for ntype in node_configs}
    for ntype, config in node_configs.items():
        for i in range(1, config["count"] + 1):
            node_id = f"{ntype}-{i}"
            nodes.append(
                {
                    "id": node_id,
                    "name": node_id,
                    "type": ntype,
                    "desc": config["desc"],
                    "battery": round(random.uniform(0.4, 1.0), 2),
                    "capacity": random.randint(10, 100),
                    "snr_uplink": 0.0,  # 稍后根据边统计填充
                    "snr_downlink": 0.0,
                    "connected_links_count": 0,
                }
            )
            node_ids_by_type[ntype].append(node_id)

    # --- 2. 边生成配置 ---
    # 策略：保证网络的层次化连通 GND-C -> BS -> UAV-R -> UAV-M -> GND-P
    # 同时随机生成少量 DISCONN (断连预警) 边

    edge_set = set()  # 防止重复边

    def add_edge(src, tgt, relation, snr_range, bw_range):
        """添加双向通信链路"""
        snr = round(random.uniform(*snr_range), 1)
        bw = round(random.uniform(*bw_range), 1)

        # 检查是否应标记为 DISCONN（SNR 极低时自动降级）
        actual_relation = relation
        if snr < 3.0:
            actual_relation = "DISCONN"

        if (src, tgt) not in edge_set:
            edges.append(
                {
                    "source": src,
                    "target": tgt,
                    "relation": actual_relation,
                    "snr": snr,
                    "bandwidth": bw,
                }
            )
            edge_set.add((src, tgt))

        if (tgt, src) not in edge_set:
            edges.append(
                {
                    "source": tgt,
                    "target": src,
                    "relation": actual_relation,
                    "snr": snr,
                    "bandwidth": bw,
                }
            )
            edge_set.add((tgt, src))

    # (1) 指挥中心连基站 (GND-C <-> BS) — 回传链路
    for gnd_c in node_ids_by_type["GND-C"]:
        for bs in random.sample(node_ids_by_type["BS"], 2):
            add_edge(gnd_c, bs, "Link_BKH", snr_range=(20, 30), bw_range=(100, 500))

    # (2) 基站连中继 (BS <-> UAV-R) — 空地链路
    for uav_r in node_ids_by_type["UAV-R"]:
        for bs in random.sample(node_ids_by_type["BS"], random.choice([1, 2])):
            add_edge(bs, uav_r, "Link_A2G", snr_range=(15, 25), bw_range=(50, 150))

    # (3) 中继之间组网 (UAV-R <-> UAV-R) — 空空链路
    for i in range(len(node_ids_by_type["UAV-R"])):
        u1 = node_ids_by_type["UAV-R"][i]
        others = [u for u in node_ids_by_type["UAV-R"] if u != u1]
        for u2 in random.sample(others, random.choice([1, 2])):
            add_edge(u1, u2, "Link_A2A", snr_range=(10, 20), bw_range=(30, 80))

    # (4) 中继连任务机 (UAV-R <-> UAV-M) — 空空链路
    for uav_m in node_ids_by_type["UAV-M"]:
        for uav_r in random.sample(node_ids_by_type["UAV-R"], random.choice([1, 2])):
            add_edge(uav_r, uav_m, "Link_A2A", snr_range=(5, 18), bw_range=(10, 50))

    # (5) 任务机连地面救援人员 (UAV-M <-> GND-P) — 空地链路
    for gnd_p in node_ids_by_type["GND-P"]:
        for uav_m in random.sample(node_ids_by_type["UAV-M"], random.choice([1, 2])):
            add_edge(uav_m, gnd_p, "Link_A2G", snr_range=(5, 15), bw_range=(5, 20))

    # (6) 侦察无人机连中继 (UAV-S <-> UAV-R) — 空空链路
    for uav_s in node_ids_by_type["UAV-S"]:
        for uav_r in random.sample(node_ids_by_type["UAV-R"], random.choice([1, 2])):
            add_edge(uav_s, uav_r, "Link_A2A", snr_range=(8, 18), bw_range=(10, 30))

    # (7) 额外的 DISCONN 边：随机选取一些节点对，模拟断连预警
    all_node_ids = [n["id"] for n in nodes]
    num_disconn = random.randint(3, 6)
    for _ in range(num_disconn):
        src = random.choice(all_node_ids)
        tgt = random.choice(all_node_ids)
        if src != tgt and (src, tgt) not in edge_set:
            add_edge(src, tgt, "DISCONN", snr_range=(0.5, 2.9), bw_range=(0.1, 2.0))

    # --- 3. 回填节点级 SNR 统计与链路计数 ---
    node_snr_up = {n["id"]: [] for n in nodes}
    node_snr_dn = {n["id"]: [] for n in nodes}
    node_link_count = {n["id"]: 0 for n in nodes}

    for e in edges:
        src, tgt = e["source"], e["target"]
        snr_val = e["snr"]
        # 出边视为上行，入边视为下行
        node_snr_up[src].append(snr_val)
        node_snr_dn[tgt].append(snr_val)
        node_link_count[src] += 1

    for node in nodes:
        nid = node["id"]
        up_vals = node_snr_up[nid]
        dn_vals = node_snr_dn[nid]
        node["snr_uplink"] = round(sum(up_vals) / len(up_vals), 1) if up_vals else 0.0
        node["snr_downlink"] = round(sum(dn_vals) / len(dn_vals), 1) if dn_vals else 0.0
        node["connected_links_count"] = node_link_count[nid]

    # --- 4. 组装并输出 ---
    kg_data = {
        "nodes": nodes,
        "edges": edges,
        "meta": {"field": "LowAltitudeUAV_Demo"},
    }

    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up 3 levels: scripts -> uav_semantic_planner -> src -> LowAltitudeUAV
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
    final_output_file = os.path.join(project_root, output_file)

    os.makedirs(os.path.dirname(final_output_file), exist_ok=True)
    with open(final_output_file, "w", encoding="utf-8") as f:
        json.dump(kg_data, f, ensure_ascii=False, indent=2)

    # 统计
    rel_counts = {}
    for e in edges:
        rel = e["relation"]
        rel_counts[rel] = rel_counts.get(rel, 0) + 1

    print("✅ 成功生成 UAV 通信网络图谱数据!")
    print(f"输出路径: {final_output_file}")
    print(f"节点总数: {len(nodes)}")
    print(f"通信链路总数: {len(edges)}")
    print(f"边类型分布: {rel_counts}")


if __name__ == "__main__":
    generate_mock_uav_data()
