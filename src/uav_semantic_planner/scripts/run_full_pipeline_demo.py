import os
import sys
import time
import json
import networkx as nx

# 添加 src 到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
src_dir = os.path.join(project_root, 'src')
if src_dir not in sys.path:
    sys.path.append(src_dir)

from uav_semantic_planner.agents.situation_assessor import SituationAssessor
from uav_semantic_planner.scripts.simulate_situational_workflow import MockAgent2_DecisionTranslator
from uav_semantic_planner.utils import UAVRoutingPlanner

def main():
    print("="*70)
    print(" 🚀 6G 语义通信：[人员被困] 场景端到端全流程模拟演示 ")
    print("="*70)
    
    # ---------------------------------------------------------
    # 阶段 1: 基础训练 (HGT, RL, SkillOpt)
    # ---------------------------------------------------------
    print("\n[阶段 1: 基础训练 (HGT, RL, SkillOpt)]")
    
    # 1.1 模拟 SkillOpt 优化阶段
    print("  >>> [SkillOpt] 正在根据大量模拟数据优化 Agent 1 的技能文档 (agent1_skill.md)...")
    time.sleep(1)
    print("  ✅ 技能文档优化完成，当前版本能够更准确地识别'强风+低电量'等边缘情况。")
    
    # 1.2 构建图谱特征提取模型 (HGT) 和 离线数据
    print("\n  >>> [HGT] 构建异构图网络缓存特征...")
    os.system(f"uv run python {os.path.join(src_dir, 'uav_semantic_planner/scripts/build_uav_graph.py')}")
    
    # 1.3 训练强化学习 (RL) 策略
    # 我们为“紧急搜救”设置专门的奖励权重（容忍低峰值，但惩罚断连）
    print("\n  >>> [RL] 开始针对救援权重的强化学习模型训练 (为节省时间，仅演示 50 epoch)...")
    os.system(f"uv run python {os.path.join(src_dir, 'uav_semantic_planner/scripts/train_uav_policy.py')} --epochs 50 --w_snr 0.5 --w_btnk 5.0 --w_stab 0.0")
    
    
    # ---------------------------------------------------------
    # 阶段 2: 态势判别 (Agent 1)
    # ---------------------------------------------------------
    print("\n[阶段 2: 态势判别 (Agent 1)]")
    print("  🚨 突发事件：侦察节点 [UAV-S-1] 通过热成像发现【人员被困】！触发态势评估机制。")
    
    skill_path = os.path.join(src_dir, "uav_semantic_planner/agents/agent1_skill.md")
    agent1 = SituationAssessor(skill_path=skill_path)
    
    # 从图谱提取当前的统计特征 (示例数据)
    mock_graph_stats = {
        "avg_snr": 8.5, 
        "disconn_count": 2
    }
    # 传感器回传的环境信息
    mock_env_info = {
        "battery_level": 0.60,
        "wind_condition": "strong"
    }
    # 目标特征信息
    mock_target_info = {
        "type": "critical_rescue",
        "T_gold_seconds": 1800  # 黄金救援时间剩余 30 分钟
    }
    
    result = agent1.assess_situation(mock_graph_stats, mock_env_info, mock_target_info)
    situation_level = result["level"]
    print(f"\n[Agent 1 评估报告]")
    print(f"  紧急度: {result.get('urgency', '?')}/5")
    print(f"  可行性: {result.get('feasibility', '?')}/5")
    print(f"  最终定级: {situation_level}")
    print(f"  分析理由: {result.get('report', '')}")
    
    
    # ---------------------------------------------------------
    # 阶段 3: 路由规划 (Agent 2 & RL Inference)
    # ---------------------------------------------------------
    print("\n[阶段 3: 语义翻译与任务通信子图规划 (Agent 2 & RL)]")
    task = "紧急搜救广播"
    weights = MockAgent2_DecisionTranslator.translate_to_reward_weights(situation_level, task)
    
    # 加载 JSON 拓扑并进行实际寻路
    json_path = os.path.join(project_root, "data/mock_uav_network.json")
    with open(json_path, encoding="utf-8") as f:
        kg_data = json.load(f)

    nx_graph = nx.DiGraph()
    for n in kg_data["nodes"]:
        nx_graph.add_node(n["id"], type=n["type"])
    for e in kg_data["edges"]:
        nx_graph.add_edge(e["source"], e["target"], relation=e["relation"], snr=e["snr"])
        
    model_pt_path = os.path.join(project_root, "checkpoints/UAV_Demo/uav_policy_final.pt")
    graph_pt_path = os.path.join(project_root, "checkpoints/UAV_Demo/uav_hetero_graph.pt")
    
    planner = UAVRoutingPlanner(
        model_pt_path=model_pt_path,
        graph_pt_path=graph_pt_path,
        device="cpu"
    )
    
    mission_spec = MockAgent2_DecisionTranslator.translate_to_mission_spec(
        situation_level, task
    )

    print(
        f"\n--- ⚡ 启动任务通信子图推演: {mission_spec.mission_id} "
        f"(SNR/备份权重: {weights}) ---"
    )
    planning_result = planner.plan_mission_communication(mission_spec, nx_graph)

    for flow_result in planning_result["flow_results"]:
        flow = flow_result["flow"]
        print(
            f"\n✅ Flow {flow['flow_id']} ({flow['purpose']}) -> "
            f"{flow_result['selected_receiver']}"
        )
        print(f"   主路径: {' -> '.join(flow_result['primary_path'])}")
        print(
            f"   主路径瓶颈 SNR: {flow_result['primary_min_snr']:.1f}dB, "
            f"备份数: {len(flow_result['backup_paths'])}"
        )
        for idx, backup_path in enumerate(flow_result["backup_paths"], start=1):
            backup_snr = flow_result["backup_min_snrs"][idx - 1]
            print(f"   备份{idx}: {' -> '.join(backup_path)} (瓶颈 {backup_snr:.1f}dB)")
        print(f"   资源预留: {flow_result['reserved_resources']}")

if __name__ == "__main__":
    main()
