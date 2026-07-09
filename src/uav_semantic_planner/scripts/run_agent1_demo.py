import os
import sys

# 添加 src 到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from uav_semantic_planner.agents.situation_assessor import SituationAssessor
from uav_semantic_planner.scripts.simulate_situational_workflow import (
    MockAgent2_DecisionTranslator,
)


def simulate_workflow():
    print("=" * 60)
    print(" 🚀 6G 语义通信态势感知全链路演示 (Powered by Ollama + SkillOpt) ")
    print("=" * 60)

    # 实例化基于真实 LLM 和技能文档的 Agent 1
    skill_path = os.path.join(os.path.dirname(__file__), "../agents/agent1_skill.md")
    agent1 = SituationAssessor(skill_path=skill_path)

    # 1. 模拟 HGT 获取到的图谱状态
    mock_graph_stats = {"avg_snr": 9.5, "disconn_count": 4}
    mock_env_info = {"battery_level": 0.45, "wind_condition": "strong"}
    mock_target_info = {"type": "critical_rescue", "T_gold_seconds": 1200}

    # 2. Agent 1 工作：态势降维分级 (调用真实大模型)
    result = agent1.assess_situation(mock_graph_stats, mock_env_info, mock_target_info)

    situation_level = result["level"]
    print("\n[Agent 1 评估报告]")
    print(f"  紧急度: {result['urgency']}/5")
    print(f"  可行性: {result['feasibility']}/5")
    print(f"  最终定级: {situation_level}")
    print(f"  分析理由: {result['report']}")

    # 3. 业务场景推演
    task = "高清视频图传"

    # Agent 2 工作：任务翻译为 RL 奖励建立函数
    weights = MockAgent2_DecisionTranslator.translate_to_reward_weights(
        situation_level, task
    )

    # 4. 底层 RL 环境执行 (模拟)
    print("\n[⚡ 底层强化学习环境 (RL Loop) 接收权重并重组路由...]")
    print("  ✓ 路由网格根据 W 参数实时更新了跳数惩罚和SNR奖励")
    print("-" * 40)


if __name__ == "__main__":
    simulate_workflow()
