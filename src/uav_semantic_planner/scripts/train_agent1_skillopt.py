import json
import os
import sys

# 添加 src 到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from uav_semantic_planner.agents.situation_assessor import SituationAssessor


def evaluate_accuracy(predictions, truths):
    """计算准确率和 MAE"""
    level_correct = 0
    u_err = 0
    f_err = 0

    for p, t in zip(predictions, truths):
        if p["level"] == t["level"]:
            level_correct += 1
        u_err += abs(p["urgency"] - t["urgency"])
        f_err += abs(p["feasibility"] - t["feasibility"])

    n = len(predictions)
    return {
        "level_accuracy": level_correct / n if n > 0 else 0,
        "urgency_mae": u_err / n if n > 0 else 0,
        "feasibility_mae": f_err / n if n > 0 else 0,
    }


def run_skillopt_loop():
    print("=" * 60)
    print(" 🚀 启动 SkillOpt 本地模拟训练循环 (Agent 1 技能优化) ")
    print("=" * 60)

    # 1. 加载数据集
    data_path = os.path.join(os.path.dirname(__file__), "../data/skillopt_dataset.json")
    if not os.path.exists(data_path):
        print(
            "未找到数据集，请先运行 python -m uav_semantic_planner.data.scenario_generator"
        )
        return

    with open(data_path, encoding="utf-8") as f:
        dataset = json.load(f)

    # 取前 10 个跑一次作为 Demo
    test_batch = dataset[:10]

    # 2. 实例化 Agent
    skill_path = os.path.join(os.path.dirname(__file__), "../agents/agent1_skill.md")
    assessor = SituationAssessor(skill_path=skill_path)

    print("\n[Phase 1: Rollout] 使用当前技能文档在测试集上执行...")
    predictions = []
    truths = []

    for i, case in enumerate(test_batch):
        print(f"  正在评估案例 {i + 1}/{len(test_batch)}...")
        pred = assessor.assess_situation(
            case["input"]["graph_stats"],
            case["input"]["env_info"],
            case["input"]["target_info"],
        )
        predictions.append(pred)
        truths.append(case["ground_truth"])

    # 3. 评估指标
    print("\n[Phase 2: Evaluate] 评估当前技能文档性能...")
    metrics = evaluate_accuracy(predictions, truths)
    print(f"  > Level 分类准确率: {metrics['level_accuracy'] * 100:.1f}%")
    print(f"  > Urgency MAE 误差: {metrics['urgency_mae']:.2f}")
    print(f"  > Feasibility MAE 误差: {metrics['feasibility_mae']:.2f}")

    print("\n[Phase 3 & 4: Reflect & Edit (模拟)]")
    print(
        "  在真实的 SkillOpt 框架中，如果准确率不够 100%，另一个 Optimizer LLM 将会："
    )
    print("  1. 对比 pred 和 truth 寻找错误规律")
    print(f"  2. 对 {skill_path} 提出文本 Patch（增删改）")
    print("  3. 在验证集上跑分，若分数提升则覆盖保存为 best_skill.md")

    print("\n✅ SkillOpt 一次迭代流程模拟完成！")


if __name__ == "__main__":
    run_skillopt_loop()
