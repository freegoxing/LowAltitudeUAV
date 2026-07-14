"""
面向低空复杂环境的态势感知与全链路协同控制推演脚本

演示完整的流水线：
HGT感知 -> Agent 1 态势评级 -> Agent 2 任务与参数翻译 -> RL 路由环境生成不同策略
"""

import random

from uav_semantic_planner.utils import (
    MissionCommunicationSpecification,
    MissionFlowSpec,
)


class MockAgent1_SituationAssessor:
    """模拟 Agent 1: 态势评估与任务分级"""

    @staticmethod
    def assess_situation(graph_stats: dict) -> str:
        """
        输入: HGT 提取的全网特征 (此处用统计量模拟)
        动作: 评估当前通信态势级别
        """
        avg_snr = graph_stats.get("avg_snr", 20.0)
        disconn_count = graph_stats.get("disconn_count", 0)

        print("\n[🤖 Agent 1 态势评估中...]")
        print(f"  > 分析全网拓扑: 平均SNR={avg_snr}dB, 断连预警数={disconn_count}")

        if disconn_count >= 5 or avg_snr < 10.0:
            level = "Level 1: 严重拥塞/断连风险 (紧急态势)"
        elif disconn_count >= 2 or avg_snr < 18.0:
            level = "Level 2: 信道波动较大 (亚健康态势)"
        else:
            level = "Level 3: 通信状况良好 (常态)"

        print(f"  > 评估结果: {level}")
        return level


class MockAgent2_DecisionTranslator:
    """模拟 Agent 2: 对话决策与参数翻译"""

    @staticmethod
    def translate_to_reward_weights(
        situation_level: str, task_type: str
    ) -> list[float]:
        """
        输入: Agent 1 的态势报告 + 用户的业务任务类型
        动作: 生成下发给底层 RL 的奖励函数权重矩阵 W=[w_snr, w_btnk, w_stab]
        """
        print("\n[🤖 Agent 2 参数翻译中...]")
        print(f"  > 接收态势: {situation_level}")
        print(f"  > 业务诉求: {task_type}")

        w_snr, w_btnk, w_stab = 1.0, 1.0, 1.0  # 默认权重

        if task_type == "高清视频图传":
            # 视频流需要极高的绝对带宽和信噪比增益，偶尔波动可以依靠缓冲忍受
            print("  > 分析推理: 视频业务属于吞吐量敏感型，需要极高峰值 SNR。")
            w_snr = 3.0
            w_btnk = 0.5
            w_stab = 0.2

        elif task_type == "无人机飞控遥测":
            # 飞控指令数据量极小，但绝不能断连，极度厌恶木桶短板和波动
            print(
                "  > 分析推理: 飞控指令属于时延与可靠性敏感型，要求木桶短板极高且绝对稳定。"
            )
            w_snr = 0.2
            w_btnk = 4.0
            w_stab = 3.0

        elif task_type == "紧急搜救广播":
            # 紧急态势下优先保证连通
            if "Level 1" in situation_level:
                print(
                    "  > 分析推理: 当前环境极度恶劣，搜救广播只求能连通即可，重罚断连。"
                )
                w_snr = 0.5
                w_btnk = 5.0
                w_stab = 0.0
            else:
                w_snr, w_btnk, w_stab = 1.5, 2.0, 1.0

        print(
            f"  > 下发底层 RL 奖励权重: W=[SNR增益:{w_snr}, 瓶颈容忍:{w_btnk}, 稳定性:{w_stab}]"
        )
        return [w_snr, w_btnk, w_stab]

    @staticmethod
    def translate_to_mission_spec(
        situation_level: str, task_type: str
    ) -> MissionCommunicationSpecification:
        """生成与设计文档一致的任务通信规范（MCS）示例。"""
        print("\n[🤖 Agent 2 任务通信规范生成中...]")
        print(f"  > 接收态势: {situation_level}")
        print(f"  > 业务诉求: {task_type}")

        return MissionCommunicationSpecification(
            mission_id="SAR-FIRE-001",
            mission_type="TASK-SAR",
            mission_priority=5,
            key_nodes=["UAV-S-1", "GND-P-1", "GND-P-2", "GND-C-1"],
            mission_flows=[
                MissionFlowSpec(
                    flow_id="F-1",
                    source="UAV-S-1",
                    receivers=["GND-P-1"],
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
                    source="UAV-S-1",
                    receivers=["GND-P-2"],
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
                    source="GND-P-1",
                    receivers=["GND-C-1"],
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
            command_receiver="GND-C-1",
        )


def simulate_workflow():
    print("=" * 60)
    print(" 🚀 6G 语义通信态势感知与路由决策流水线模拟启动 ")
    print("=" * 60)

    # 1. 模拟 HGT 获取到的图谱状态
    mock_graph_stats = {
        "avg_snr": round(random.uniform(8.0, 25.0), 1),
        "disconn_count": random.randint(0, 7),
    }

    # 2. Agent 1 工作：态势降维分级
    situation_level = MockAgent1_SituationAssessor.assess_situation(mock_graph_stats)

    # 3. 不同的业务场景推演
    tasks = ["高清视频图传", "无人机飞控遥测"]

    for task in tasks:
        # Agent 2 工作：任务翻译为 RL 奖励建立函数
        MockAgent2_DecisionTranslator.translate_to_reward_weights(situation_level, task)

        # 4. 底层 RL 环境执行 (模拟)
        print("\n[⚡ 底层强化学习环境 (RL Loop) 接收权重并重组路由...]")
        if task == "高清视频图传":
            print(
                "  ✓ RL 探索收敛倾向: 优先挑选距离基站近、无遮挡的主干链路，哪怕这些链路偶尔不稳定。"
            )
        else:
            print(
                "  ✓ RL 探索收敛倾向: 放弃峰值高的短直飞链路，选择通过多个 UAV-R (中继) 绕开干扰源，寻找最平稳的安全链路。"
            )
        print("-" * 40)


if __name__ == "__main__":
    simulate_workflow()
