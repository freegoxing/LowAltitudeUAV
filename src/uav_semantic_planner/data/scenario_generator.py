import json
import os
import random


def generate_skillopt_dataset(
    num_samples: int = 100, output_file: str = "skillopt_dataset.json"
):
    """
    生成用于 SkillOpt 训练的模拟场景数据集。
    包含输入态势特征和 ground truth 标签。
    """
    dataset = []

    for i in range(num_samples):
        # 1. 随机生成环境状态
        avg_snr = round(random.uniform(2.0, 25.0), 1)
        disconn_count = random.randint(0, 10)
        battery = round(random.uniform(0.1, 1.0), 2)
        wind = random.choice(["calm", "breeze", "strong", "heavy"])
        t_gold = random.choice([600, 1800, 3600, 7200, 86400])
        target_type = random.choice(
            ["critical_rescue", "material_delivery", "routine_patrol", "recon"]
        )

        # 2. 计算 Ground Truth (基于我们期望的完美逻辑)
        urgency = 3
        if target_type == "critical_rescue":
            urgency = 5 if t_gold <= 1800 else 4
        elif target_type == "material_delivery":
            urgency = 3
        else:
            urgency = 2

        feasibility = 3
        if avg_snr > 18 and disconn_count == 0 and battery > 0.6:
            feasibility = 5
        elif avg_snr < 10 or disconn_count >= 3 or battery < 0.3 or wind == "heavy":
            feasibility = 2
            if battery < 0.2 or wind == "heavy":
                feasibility = 1

        # Level 逻辑
        if wind == "heavy" and battery < 0.2:
            level = "Level_3"
        elif feasibility <= 1:
            level = "Level_3"
        elif urgency >= 4 and feasibility < 3:
            level = "Level_1"
        else:
            level = "Level_2"

        # 3. 组装用例
        case = {
            "id": f"scenario_{i:03d}",
            "input": {
                "graph_stats": {"avg_snr": avg_snr, "disconn_count": disconn_count},
                "env_info": {"battery_level": battery, "wind_condition": wind},
                "target_info": {"type": target_type, "T_gold_seconds": t_gold},
            },
            "ground_truth": {
                "urgency": urgency,
                "feasibility": feasibility,
                "level": level,
            },
        }
        dataset.append(case)

    # 保存
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"✅ 生成了 {num_samples} 个 SkillOpt 模拟训练数据到 {output_file}")


if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(__file__), "skillopt_dataset.json")
    generate_skillopt_dataset(150, out_path)
