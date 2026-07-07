import json
import os
import random


def generate_mock_uav_data(output_file="data/mock_uav_network.json"):
    """
    生成一个用于 Demo 的轻量级低空无人机通信网络图谱
    """
    nodes = []
    edges = []

    # --- 1. 节点生成配置 ---
    # 定义节点类型与数量
    node_configs = {
        "GND-C": {"count": 2, "desc": "地面指挥车"},
        "BS": {"count": 4, "desc": "基站"},
        "UAV-R": {"count": 8, "desc": "中继无人机"},
        "UAV-M": {"count": 10, "desc": "任务无人机"},
        "GND-P": {"count": 5, "desc": "地面救援人员(终端)"},
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
                    "type": ntype,  # 节点类型
                    "desc": config["desc"],
                    "battery": round(random.uniform(0.4, 1.0), 2),
                    "capacity": random.randint(10, 100),
                }
            )
            node_ids_by_type[ntype].append(node_id)

    # --- 2. 边生成配置 ---
    # 定义合法的连接模式与关系名称
    # 策略：保证网络的层次化连通 GND-C -> BS -> UAV-R -> UAV-M -> GND-P

    def add_edge(src, tgt, relation, snr_range, bw_range):
        snr = round(random.uniform(*snr_range), 1)
        bw = round(random.uniform(*bw_range), 1)
        # 双向通信链路
        edges.append(
            {
                "source": src,
                "target": tgt,
                "relation": relation,
                "snr": snr,
                "bandwidth": bw,
            }
        )
        edges.append(
            {
                "source": tgt,
                "target": src,
                "relation": relation,
                "snr": snr,
                "bandwidth": bw,
            }
        )

    # (1) 指挥中心连基站 (GND-C <-> BS)
    for gnd_c in node_ids_by_type["GND-C"]:
        # 每个指挥中心连2个基站
        for bs in random.sample(node_ids_by_type["BS"], 2):
            add_edge(gnd_c, bs, "Link_BKH", snr_range=(20, 30), bw_range=(100, 500))

    # (2) 基站连中继 (BS <-> UAV-R)
    for uav_r in node_ids_by_type["UAV-R"]:
        # 每个中继连1-2个基站
        for bs in random.sample(node_ids_by_type["BS"], random.choice([1, 2])):
            add_edge(bs, uav_r, "Link_A2G", snr_range=(15, 25), bw_range=(50, 150))

    # (3) 中继之间组网 (UAV-R <-> UAV-R)
    for i in range(len(node_ids_by_type["UAV-R"])):
        u1 = node_ids_by_type["UAV-R"][i]
        # 随机连1-2个其他中继
        others = [u for u in node_ids_by_type["UAV-R"] if u != u1]
        for u2 in random.sample(others, random.choice([1, 2])):
            add_edge(u1, u2, "Link_A2A", snr_range=(10, 20), bw_range=(30, 80))

    # (4) 中继连任务机 (UAV-R <-> UAV-M)
    for uav_m in node_ids_by_type["UAV-M"]:
        # 每个任务机连1-2个中继
        for uav_r in random.sample(node_ids_by_type["UAV-R"], random.choice([1, 2])):
            add_edge(uav_r, uav_m, "Link_A2A", snr_range=(5, 18), bw_range=(10, 50))

    # (5) 任务机连地面救援人员 (UAV-M <-> GND-P)
    for gnd_p in node_ids_by_type["GND-P"]:
        # 每个终端连1-2个任务机
        for uav_m in random.sample(node_ids_by_type["UAV-M"], random.choice([1, 2])):
            add_edge(uav_m, gnd_p, "Link_A2G", snr_range=(5, 15), bw_range=(5, 20))

    # 组装数据
    kg_data = {"nodes": nodes, "edges": edges, "meta": {"field": "LowAltitudeUAV_Demo"}}

    # 写入文件
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    final_output_file = os.path.join(project_root, output_file)

    os.makedirs(os.path.dirname(final_output_file), exist_ok=True)
    with open(final_output_file, "w", encoding="utf-8") as f:
        json.dump(kg_data, f, ensure_ascii=False, indent=2)

    print("✅ 成功生成 UAV Mock 通信网络数据!")
    print(f"输出路径: {final_output_file}")
    print(f"节点总数: {len(nodes)}")
    print(f"通信单向链路总数: {len(edges)}")


if __name__ == "__main__":
    generate_mock_uav_data()
