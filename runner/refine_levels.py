import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Any

import numpy as np

# 自动处理路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def refine_levels(
    target_field: str,
    data_dir: str,
    kg_data_path: str,
    output_file: str | None = None,
) -> None:
    """
    对特定领域的 LLM 定级结果进行图结构校准和精炼
    Refine LLM concept levels using graph topology to correct hallucinations.
    """
    print(
        f"=== 启动 LLM 等级细化与幻觉修正 (Graph-based Refinement) - 领域: {target_field} ==="
    )

    # 动态构建输入输出路径
    levels_file = os.path.join(data_dir, f"concept_levels_{target_field}.json")
    if not output_file:
        output_file = os.path.join(
            data_dir, f"concept_levels_{target_field}_refined.json"
        )

    if not os.path.exists(kg_data_path):
        print(f"错误: 缺少知识图谱文件 {kg_data_path}，请先运行 build_graph.py")
        return

    if not os.path.exists(levels_file):
        print(
            f"错误: 缺少定级文件 {levels_file}，请确保已运行 rank_concepts_by_level.py --field '{target_field}'"
        )
        return

    # 加载数据
    with open(kg_data_path, encoding="utf-8") as f:
        kg_data = json.load(f)

    with open(levels_file, encoding="utf-8") as f:
        llm_levels: dict[str, Any] = json.load(f)

    nodes = kg_data["nodes"]
    edges = kg_data["edges"]

    # 强制将所有 ID 转换为字符串，以确保匹配一致性
    id_to_name = {str(n["id"]): n["name"] for n in nodes}
    str_llm_levels = {str(k): v for k, v in llm_levels.items()}

    # 处理 ID 不匹配问题
    graph_ids = set(id_to_name.keys())
    level_ids = set(str_llm_levels.keys())
    common_ids = graph_ids.intersection(level_ids)

    unmatched_in_graph = graph_ids - level_ids
    unmatched_in_levels = level_ids - graph_ids

    if unmatched_in_graph:
        print(
            f"警告: 图中有 {len(unmatched_in_graph)} 个节点在定级文件中未找到，将使用默认等级 5"
        )
    if unmatched_in_levels:
        print(
            f"注意: 定级文件中有 {len(unmatched_in_levels)} 个 ID 未在当前图中出现，将被忽略"
        )

    # 初始化等级映射，默认值为 5
    id_to_llm_level: dict[str, int] = {node_id: 5 for node_id in graph_ids}
    for node_id in common_ids:
        try:
            id_to_llm_level[node_id] = int(float(str_llm_levels[node_id]))
        except (ValueError, TypeError):
            id_to_llm_level[node_id] = 5

    # 1. 构建邻接关系 (仅先修关系)
    in_neighbors = defaultdict(list)
    out_neighbors = defaultdict(list)

    for edge in edges:
        if edge.get("relation") == "prerequisite":
            u, v = str(edge["source"]), str(edge["target"])
            out_neighbors[u].append(v)
            in_neighbors[v].append(u)

    # 2. 计算拓扑得分 (基于入度/出度比率，平滑处理)
    # Score 越高，越倾向于基础概念；Score 越低，越倾向于高阶概念
    topo_scores: dict[str, float] = {}
    for node_id in graph_ids:
        out_deg = len(out_neighbors[node_id])
        in_deg = len(in_neighbors[node_id])
        total = out_deg + in_deg
        if total == 0:
            topo_scores[node_id] = 0.0
        else:
            topo_scores[node_id] = float((out_deg - in_deg) / (total + 5))

    # 3. 识别并修正明显 LLM 幻觉
    refined_levels = id_to_llm_level.copy()
    adjustments: list[tuple[str, int, int, float, str]] = []

    for node_id in common_ids:
        llm_lvl = id_to_llm_level[node_id]
        score = topo_scores.get(node_id, 0.0)
        suggested_lvl = llm_lvl

        # Case A: LLM 认为太难，但图结构显示它很基础
        if llm_lvl >= 6 and score > 0.3:
            suggested_lvl = max(2, llm_lvl - 3)
            adjustments.append(
                (
                    id_to_name[node_id],
                    llm_lvl,
                    suggested_lvl,
                    score,
                    "LLM偏难(图显示为基础)",
                )
            )

        # Case B: LLM 认为太易，但图结构显示它很高级
        elif llm_lvl <= 3 and score < -0.5:
            suggested_lvl = min(8, llm_lvl + 3)
            adjustments.append(
                (
                    id_to_name[node_id],
                    llm_lvl,
                    suggested_lvl,
                    score,
                    "LLM偏易(图显示为进阶)",
                )
            )

        refined_levels[node_id] = suggested_lvl

    # 4. 邻居平滑 (Neighbor Smoothing) - 增强版，支持单边约束
    final_levels: dict[str, int] = {}
    for node_id in graph_ids:
        current_lvl = refined_levels[node_id]

        preds = in_neighbors[node_id]
        succs = out_neighbors[node_id]

        if not preds and not succs:
            final_levels[node_id] = current_lvl
            continue

        p_levels = [refined_levels[p] for p in preds if p in refined_levels]
        s_levels = [refined_levels[s] for s in succs if s in refined_levels]

        new_lvl = current_lvl

        # 综合考虑先修和后续的约束
        if p_levels and s_levels:
            # 双向约束
            lower_bound = np.percentile(p_levels, 25)
            upper_bound = np.percentile(s_levels, 75)

            if current_lvl < lower_bound - 1:
                new_lvl = int(np.round((current_lvl + lower_bound) / 2))
            elif current_lvl > upper_bound + 1:
                new_lvl = int(np.round((current_lvl + upper_bound) / 2))
        elif p_levels:
            # 只有先修：当前等级不能比先修低太多
            p_min_threshold = np.percentile(p_levels, 25)
            if current_lvl < p_min_threshold:
                new_lvl = int(np.round((current_lvl + p_min_threshold) / 2))
        elif s_levels:
            # 只有后继：当前等级不能比后继高太多
            s_max_threshold = np.percentile(s_levels, 75)
            if current_lvl > s_max_threshold:
                new_lvl = int(np.round((current_lvl + s_max_threshold) / 2))

        final_levels[node_id] = new_lvl

    # 统计与保存
    print(f"--- 修正完成 ({target_field}) ---")
    print(f"处理节点总数: {len(graph_ids)}")
    print(f"检测到明显幻觉并修正的节点数: {len(adjustments)}")
    if adjustments:
        print("Top 5 修正案例:")
        # 按修正幅度排序
        sorted_adjusts = sorted(
            adjustments, key=lambda x: abs(x[1] - x[2]), reverse=True
        )
        for name, old, new, score, reason in sorted_adjusts[:5]:
            print(
                f"  - {name}: L{old} -> L{new} (TopoScore: {score:.2f}) | 原因: {reason}"
            )

    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_levels, f, ensure_ascii=False, indent=2)

    print(f"精炼后的等级已保存至: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="LLM 等级细化与修正工具")
    parser.add_argument(
        "--field", type=str, default="心理学", help="目标领域 (默认: 心理学)"
    )
    parser.add_argument(
        "--data_dir", type=str, default="data/MOOCCubex", help="数据目录"
    )
    parser.add_argument("--kg_data_file", type=str, help="知识图谱路径 (默认自动推导)")
    parser.add_argument("--output_file", type=str, help="输出文件路径 (可选)")
    args = parser.parse_args()

    if not args.kg_data_file:
        args.kg_data_file = os.path.join(args.data_dir, f"kg_data_{args.field}.json")

    refine_levels(args.field, args.data_dir, args.kg_data_file, args.output_file)


if __name__ == "__main__":
    main()
