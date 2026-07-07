import os
import sys
import json
import argparse
from typing import Dict, List, Any, Optional, Tuple

# 自动处理路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from hgt_rl_planner.data_loader import load_mooccubex_subgraph


def run_quality_gate(
    kg_data: Dict[str, Any], 
    max_total_violation_rate: float, 
    max_severe_violation_rate: float, 
    severe_threshold: int,
    max_missing_level_rate: float = 0.1,
    min_valid_level: int = 1,
    max_valid_level: int = 10
) -> None:
    """
    按先修关系与概念等级的一致性进行质量门控。
    Perform quality gate check based on consistency between prerequisites and concept levels.
    """
    nodes = kg_data.get("nodes", [])
    edges = kg_data.get("edges", [])
    level_by_id: Dict[str, int] = {}
    name_by_id: Dict[str, str] = {}
    invalid_level_ids: List[Tuple[str, Any, str]] = [] # (id, value, reason)

    for n in nodes:
        nid = n.get("id")
        if not nid:
            continue
        name_by_id[nid] = n.get("name", nid)
        raw_level = n.get("level")
        
        parsed_level: Optional[int] = None
        if raw_level is not None:
            try:
                parsed_level = int(float(raw_level))
                # 范围校验
                if parsed_level < min_valid_level or parsed_level > max_valid_level:
                    invalid_level_ids.append((nid, raw_level, f"越界(需在{min_valid_level}-{max_valid_level}之间)"))
                    parsed_level = None
            except (TypeError, ValueError):
                invalid_level_ids.append((nid, raw_level, "无法解析为数值"))
        else:
            invalid_level_ids.append((nid, "None", "缺失"))

        # 如果是非法或缺失，降级处理但会计入统计
        level_by_id[nid] = parsed_level if parsed_level is not None else 5

    total_nodes = len(nodes)
    invalid_rate = len(invalid_level_ids) / max(1, total_nodes)
    
    print("=== 质量门控报告 ===")
    print(f"节点总数: {total_nodes}")
    print(f"缺失或非法等级节点数: {len(invalid_level_ids)} ({invalid_rate:.2%})")

    if invalid_level_ids:
        print("部分异常等级示例:")
        for nid, val, reason in invalid_level_ids[:5]:
            print(f"  - ID: {nid}, Name: {name_by_id.get(nid)}, Value: {val}, Reason: {reason}")

    if invalid_rate > max_missing_level_rate:
        print(f"错误: 缺失或非法等级的节点比例 ({invalid_rate:.2%}) 超过阈值 ({max_missing_level_rate:.2%})")
        raise RuntimeError(f"质量门控未通过: 缺失/非法等级比例过高 ({invalid_rate:.2%})")

    prereq_edges = [e for e in edges if e.get("relation") == "prerequisite"]
    if not prereq_edges:
        print("[质量门控] 未检测到 prerequisite 边，跳过一致性检查。")
        return

    violations = []
    severe_violations = []
    for e in prereq_edges:
        src = e.get("source")
        tgt = e.get("target")
        if src not in level_by_id or tgt not in level_by_id:
            continue

        diff = level_by_id[tgt] - level_by_id[src]
        if diff < 0:
            record = {
                "source": src,
                "target": tgt,
                "src_name": name_by_id.get(src, src),
                "tgt_name": name_by_id.get(tgt, tgt),
                "src_level": level_by_id[src],
                "tgt_level": level_by_id[tgt],
                "diff": diff,
            }
            violations.append(record)
            if diff <= severe_threshold:
                severe_violations.append(record)

    total_prereqs = len(prereq_edges)
    violation_rate = len(violations) / max(1, total_prereqs)
    severe_rate = len(severe_violations) / max(1, total_prereqs)

    print(f"prerequisite 总数: {total_prereqs}")
    print(f"违规数(diff<0): {len(violations)} ({violation_rate:.2%})")
    print(
        f"严重违规数(diff<={severe_threshold}): {len(severe_violations)} "
        f"({severe_rate:.2%})"
    )

    if severe_violations:
        print("严重违规 Top 10:")
        for item in sorted(severe_violations, key=lambda x: x["diff"])[:10]:
            print(
                f"  - [{item['src_name']}(L{item['src_level']})] -> "
                f"[{item['tgt_name']}(L{item['tgt_level']})], diff={item['diff']}"
            )

    if violation_rate > max_total_violation_rate or severe_rate > max_severe_violation_rate:
        raise RuntimeError(
            "质量门控未通过: "
            f"违规率={violation_rate:.2%}(阈值 {max_total_violation_rate:.2%}), "
            f"严重违规率={severe_rate:.2%}(阈值 {max_severe_violation_rate:.2%})"
        )


def main():
    parser = argparse.ArgumentParser(description="MOOCCubex 异构图离线构建工具")
    parser.add_argument("--data_dir", type=str, default="data/MOOCCubex", help="原始数据目录")
    parser.add_argument("--field", type=str, default="心理学", help="目标领域")
    parser.add_argument("--output_file", type=str, help="输出文件路径 (默认自动推导)")
    parser.add_argument(
        "--enable_quality_gate",
        action="store_true",
        help="启用先修-等级一致性质检，超阈值会拒绝保存图文件",
    )
    parser.add_argument(
        "--max_total_violation_rate",
        type=float,
        default=0.30,
        help="允许的总违规率上限 (diff<0)",
    )
    parser.add_argument(
        "--max_severe_violation_rate",
        type=float,
        default=0.02,
        help="允许的严重违规率上限 (diff<=severe_threshold)",
    )
    parser.add_argument(
        "--severe_threshold",
        type=int,
        default=-3,
        help="严重违规阈值 (diff<=该值视为严重违规)",
    )
    parser.add_argument(
        "--max_missing_level_rate",
        type=float,
        default=0.20,
        help="允许的缺失等级节点比例上限",
    )
    args = parser.parse_args()

    if not args.output_file:
        args.output_file = os.path.join(args.data_dir, f"kg_data_{args.field}.json")

    print(f"=== 启动离线图构建: [{args.field}] ===")

    # 1. 调用已有的加载器
    kg_data, meta = load_mooccubex_subgraph(args.data_dir, args.field)

    # 2. 补充元数据
    kg_data["meta"] = meta

    # 2.5 构建前质检
    if args.enable_quality_gate:
        run_quality_gate(
            kg_data,
            max_total_violation_rate=args.max_total_violation_rate,
            max_severe_violation_rate=args.max_severe_violation_rate,
            severe_threshold=args.severe_threshold,
            max_missing_level_rate=args.max_missing_level_rate
        )

    # 3. 保存为标准 JSON
    output_dir = os.path.dirname(os.path.abspath(args.output_file))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    with open(args.output_file, 'w', encoding='utf-8') as f:
        json.dump(kg_data, f, ensure_ascii=False, indent=2)

    print(f"=== 构建完成！缓存已保存至: {args.output_file} ===")
    print(f"--- 节点总数: {len(kg_data['nodes'])}")
    print(f"--- 边总数: {len(kg_data['edges'])}")


if __name__ == "__main__":
    main()
