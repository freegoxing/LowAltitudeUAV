"""
数据加载模块

本模块仅负责从磁盘读取原始知识图谱数据，
包括自定义 JSON 格式数据以及标准三元组格式数据集。
模块内不包含任何数据清洗、预处理或结构转换逻辑，
相关处理功能请参阅 `data_utils.py`。

该模块主要用于为后续的 Pre-HGT 编码与强化学习训练流程
提供统一、可靠的数据输入接口。
"""

import json
import os
from typing import Any


# --- 类型注释 ---
class NodesData(dict[str, Any]):
    """单个节点的结构定义"""

    pass


class EdgesData(dict[str, Any]):
    """单条边的结构定义"""

    pass


class KnowledgeGraph(dict[str, list]):
    """知识图谱JSON文件的整体结构"""

    pass


def _pick_first_existing_path(candidate_paths: list[str]) -> tuple[str, bool]:
    """从候选路径中选择第一个存在的文件。"""
    for path in candidate_paths:
        if os.path.exists(path):
            return path, True
    return candidate_paths[-1], False


# --- 内部辅助函数 ---


def _scan_mooccubex_concepts(
    data_dir: str, target_field: str
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """
    统一扫描 MOOCCubex 概念文件的逻辑。

    Returns:
        Tuple[Dict[str, str], Dict[str, List[str]]]: (id_to_name, name_to_ids)
    """
    concept_json_path = os.path.join(data_dir, "entities", "concept.json")
    if not os.path.exists(concept_json_path):
        raise FileNotFoundError(f"找不到原始数据文件: {concept_json_path}")

    all_target_concepts = {}  # id -> name
    name_to_ids = {}  # name -> list of ids
    with open(concept_json_path, encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            # 核心过滤逻辑：ID 必须以目标领域结尾
            if item["id"].endswith(f"_{target_field}"):
                c_id = item["id"]
                c_name = item["name"]

                # 使用 ID 作为唯一键，避免同名不同概念冲突
                if c_id not in all_target_concepts:
                    all_target_concepts[c_id] = c_name
                    if c_name not in name_to_ids:
                        name_to_ids[c_name] = []
                    name_to_ids[c_name].append(c_id)
    return all_target_concepts, name_to_ids


# --- 加载器 ---


def extract_concept_dict_by_field(data_dir: str, target_field: str) -> dict[str, str]:
    """
    从 MOOCCubex 概念文件中提取指定领域的概念字典 (ID -> Name)。

    Args:
        data_dir (str): 数据集根目录 (包含 entities/concept.json)。
        target_field (str): 目标学科领域 (如 "计算机科学与技术"、"心理学")。

    Returns:
        Dict[str, str]: 概念 ID 到名称的映射字典。
    """
    all_target_concepts, _ = _scan_mooccubex_concepts(data_dir, target_field)
    return all_target_concepts


def load_custom_kg_from_json(file_path: str) -> KnowledgeGraph:
    """
    从 JSON 文件加载自定义格式的知识图谱数据。

    Args:
        file_path (str): 知识图谱 JSON 文件的路径 (通常为 kg_data_{field}.json)。

    Returns:
        KnowledgeGraph: 加载后的数据，以字典形式表示。
    """
    print(f"--- 正在从 {file_path} 加载自定义知识图谱 ---")
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    return data


def load_triplets_from_file(file_path: str) -> list[tuple[str, str, str]]:
    """
    从文本文件加载三元组。
    文件格式应为：头实体\t关系\t尾实体\n
    Args:
        file_path (str): 三元组文件的路径。

    Returns:
        List[Tuple[str, str, str]]: 字符串三元组列表。
    """
    triplets = []
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            try:
                # Nell-995 的格式是 concept:h\tconcept:r\tconcept:t
                # 我们在这里直接分割，保持原始字符串
                parts = line.strip().split("\t")
                if len(parts) == 3:
                    triplets.append((parts[0], parts[1], parts[2]))
                else:
                    print(f"警告: 跳过格式不正确的行 -> {line.strip()}")
            except ValueError:
                print(f"警告: 跳过格式不正确的行 -> {line.strip()}")
    return triplets


def load_standard_dataset(
    dataset_path: str,
) -> tuple[
    list[tuple[str, str, str]], list[tuple[str, str, str]], list[tuple[str, str, str]]
]:
    """
    从目录加载一个标准的知识图谱数据集。
    该函数会查找并加载 train.txt, valid.txt, 和 test.txt 文件。
    """
    print(f"--- 正在从 '{dataset_path}' 加载标准数据集文件 ---")

    absolute_dataset_path = os.path.abspath(dataset_path)
    print(f"--- 解析后的绝对路径: {absolute_dataset_path} ---")

    if not os.path.isdir(absolute_dataset_path):
        print(f"--- 错误: 路径 '{absolute_dataset_path}' 不是一个有效的目录。 ---")
        raise FileNotFoundError(f"数据集目录不存在: {absolute_dataset_path}")

    print(
        f"--- 目录 '{absolute_dataset_path}' 中的内容: {os.listdir(absolute_dataset_path)} ---"
    )

    splits = ["train", "valid", "test"]
    loaded_triplets = []

    for split_name in splits:
        # 考虑到某些数据集的文件名可能是 entities.txt, relations.txt
        # 但这里严格按照 train/valid/test.txt 的约定
        file_path = os.path.join(dataset_path, f"{split_name}.txt")

        absolute_file_path = os.path.abspath(file_path)
        print(f"--- 正在检查文件: {absolute_file_path} ---")

        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"错误: 在 '{dataset_path}' 中未找到文件 '{os.path.basename(file_path)}'。"
                f"请确保数据集已按要求解压，并且文件名正确 (train.txt, valid.txt, test.txt)。"
            )

        triplets = load_triplets_from_file(file_path)
        print(f"  - 已加载 {len(triplets)} 个三元组从 {os.path.basename(file_path)}")
        loaded_triplets.append(triplets)

    return tuple(loaded_triplets)


def load_mooccubex_subgraph(
    data_dir: str, target_field: str = "心理学"
) -> tuple[KnowledgeGraph, dict[str, str]]:
    """
    主干+上下文 (Backbone & Flesh) 异构图加载器：
    - Backbone (主干): 具有先修关系的核心节点，受 M_pre 强约束。
    - Flesh (血肉): 通过共现引入的扩展节点，受 HGT Attention 驱动。
    """
    print(f"--- 正在提取 MOOCCubex [{target_field}] 主干+血肉异构图 ---")
    ent_dir = os.path.join(data_dir, "entities")
    rel_dir = os.path.join(data_dir, "relations")

    # 动态映射学科到先修关系文件 (高优先级修复)
    field_to_prereq = {
        "计算机科学与技术": "cs.json",
        "心理学": "psy.json",
        "数学": "math.json",
    }
    prereq_filename = field_to_prereq.get(target_field)
    if not prereq_filename:
        raise ValueError(
            f"未知的目标领域: {target_field}，请在 field_to_prereq 中补充对应的先修文件名。"
        )
    prereq_path = os.path.join(data_dir, "prerequisites", prereq_filename)

    # 1. 扫描目标领域所有概念
    print(f"--- 正在预扫描 [{target_field}] 领域概念 ---")
    all_target_concepts, name_to_ids = _scan_mooccubex_concepts(data_dir, target_field)

    # 2. 识别主干节点 (Backbone)
    backbone_ids = set()
    prereq_edges = []
    if os.path.exists(prereq_path):
        print("--- 正在提取主干节点与先修约束 ---")

        # 第一阶段：只收集 ground_truth=±1 的确认关系
        # 注意：ground_truth = -1 表示 c1 是后修概念，c2 是先修概念，需要反转方向
        # 忽略 ground_truth=0 的预测结果，只使用高质量的人工标注数据
        candidate_edges = {}  # (c1, c2) -> (is_ground_truth, score, direction_reversed)
        print("  - 正在读取先修关系数据...")
        line_count = 0
        valid_count = 0
        with open(prereq_path, encoding="utf-8") as f:
            for line in f:
                line_count += 1
                if line_count % 100000 == 0:
                    print(f"    已处理 {line_count} 行...")

                item = json.loads(line)
                c1, c2 = item["c1"], item["c2"]
                if c1 in name_to_ids and c2 in name_to_ids:
                    gt = item.get("ground_truth", 0)

                    if gt == 1:
                        # c1 -> c2 (正常方向)
                        candidate_edges[(c1, c2)] = (True, 1.0, False)
                        valid_count += 1
                    elif gt == -1:
                        # c2 -> c1 (需要反转)
                        candidate_edges[(c2, c1)] = (True, 1.0, False)
                        valid_count += 1
                    # 忽略 ground_truth=0 的预测结果

        print(f"  - 总共读取 {line_count} 行，其中 {valid_count} 条有效先修关系")

        # 第二阶段：处理矛盾关系（降级策略）
        # 问题：ground_truth=-1 的数据中存在大量双向冲突（278,438 对）
        # 解决方案：降级策略 + 保持单向性
        #   1. 保留所有 ground_truth=1 的关系（514 条高质量数据，is_gt=True）
        #   2. 对于 ground_truth=-1 的关系：
        #      - 如果没有双向冲突：保留为高质量数据（is_gt=True）
        #      - 如果有双向冲突：保留字典序较小的方向，降级为预测数据（is_gt=False），删除反向
        #   最终：保持图的单向性，让 HGT attention 学习权重
        print("  - 正在处理矛盾关系（降级策略 + 保持单向性）...")

        # 收集原始的 ground_truth 信息，区分来源
        pair_source = {}  # (c1, c2) -> 'gt_1' or 'gt_minus_1'
        print("    - 重新扫描原始数据...")

        with open(prereq_path, encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                c1, c2 = item["c1"], item["c2"]
                if c1 in name_to_ids and c2 in name_to_ids:
                    gt = item.get("ground_truth", 0)
                    if gt == 1:
                        pair_source[(c1, c2)] = "gt_1"
                    elif gt == -1:
                        pair_source[(c2, c1)] = "gt_minus_1"  # 反转后

        # 找出 ground_truth=-1 中的双向冲突，并决定保留哪个方向
        gt_minus_1_pairs = [k for k, v in pair_source.items() if v == "gt_minus_1"]
        to_remove = set()  # 要删除的关系对
        to_downgrade = set()  # 要降级的关系对

        print("    - 正在检测 ground_truth=-1 中的双向冲突...")
        for pair in gt_minus_1_pairs:
            reverse_pair = (pair[1], pair[0])
            if (
                reverse_pair in pair_source
                and pair_source[reverse_pair] == "gt_minus_1"
            ):
                # 双向冲突：保留字典序较小的，删除较大的
                if pair < reverse_pair:
                    to_remove.add(reverse_pair)  # 删除反向的
                    to_downgrade.add(pair)  # 降级保留的
                else:
                    to_remove.add(pair)  # 删除正向的
                    to_downgrade.add(reverse_pair)  # 降级保留的

        print(f"    - 发现 {len(to_remove)} 条冲突关系将被删除")
        print(f"    - 发现 {len(to_downgrade)} 条冲突关系将被降级为预测数据")

        # 降级策略：将冲突的关系标记为 is_gt=False，并删除双向关系
        final_prereq_pairs = {}
        for (c1, c2), (is_gt, score, _) in candidate_edges.items():
            if (c1, c2) in to_remove:
                # 删除这个方向
                continue
            elif (c1, c2) in to_downgrade:
                # 降级为预测数据
                final_prereq_pairs[(c1, c2)] = (False, 0.5)
            else:
                # 保留原始状态
                final_prereq_pairs[(c1, c2)] = (is_gt, score)

        # 统计处理结果
        original_count = len(candidate_edges)
        final_count = len(final_prereq_pairs)
        removed_conflicts = original_count - final_count

        if removed_conflicts > 0:
            print(
                f"  - 检测到 {removed_conflicts // 2} 对矛盾的先修关系，已保留字典序较小的方向"
            )

        # 第三阶段：转换为最终的边列表
        print("  - 正在生成最终的边列表...")
        ground_truth_count = 0
        predicted_count = 0
        edge_count = 0

        for (c1, c2), (is_gt, score) in final_prereq_pairs.items():
            edge_count += 1
            if edge_count % 50000 == 0:
                print(f"    - 已生成 {edge_count} 条边...")

            # 为避免同名多ID导致的笛卡尔积边数爆炸，这里采取“保守降维”策略：
            # 即使同一领域内有多个同名正统ID，我们也只选取首个ID进行连接，
            # 放弃后续实体的先修信息，以防止引入缺乏真实标注支撑的弱真值边使图谱过度稠密化。
            id1 = name_to_ids[c1][0]
            id2 = name_to_ids[c2][0]
            prereq_edges.append(
                {"source": id1, "target": id2, "relation": "prerequisite"}
            )
            backbone_ids.add(id1)
            backbone_ids.add(id2)

            if is_gt:
                ground_truth_count += 1
            else:
                predicted_count += 1

        print(
            f"  - 最终先修关系统计: ground_truth={ground_truth_count}, predicted={predicted_count}"
        )

    print(f"  - 主干节点数 (Backbone): {len(backbone_ids)}")
    print(f"  - 先修关系边数 (Prerequisite): {len(prereq_edges)}")

    # 3. 提前加载分类和等级数据 (用于指导全局 DAG 构建)
    # 优先使用经过校验/修正的数据文件，降低 LLM 幻觉直接入图的风险。
    cat_candidates = [
        os.path.join(data_dir, f"concept_categories_{target_field}_verified.json"),
        os.path.join(data_dir, f"concept_categories_{target_field}.json"),
    ]
    level_candidates = [
        os.path.join(data_dir, f"concept_levels_{target_field}_trusted.json"),
        os.path.join(data_dir, f"concept_levels_{target_field}_refined.json"),
        os.path.join(data_dir, f"concept_levels_{target_field}.json"),
    ]
    cat_path, cat_found = _pick_first_existing_path(cat_candidates)
    level_path, level_found = _pick_first_existing_path(level_candidates)

    cat_map = {}
    if cat_found:
        with open(cat_path, encoding="utf-8") as f:
            cat_map = json.load(f)
        print(f"--- 分类文件: {os.path.basename(cat_path)} ---")
    else:
        print("--- 未检测到分类文件，使用默认类型 Theory ---")

    level_map = {}
    if level_found:
        with open(level_path, encoding="utf-8") as f:
            level_map = json.load(f)
        print(f"--- 等级文件: {os.path.basename(level_path)} ---")
    else:
        print("--- 未检测到等级文件，使用默认等级 5 ---")

    # 4. 提取共现关系并识别血肉节点 (Flesh)
    from collections import Counter

    co_occur_configs = {
        "taught_together": ("concept-video.txt", 2),
        "tested_together": ("concept-problem.txt", 1),
        "cited_together": ("concept-paper.txt", 2),
        "discussed_together": ("concept-comment.txt", 1),
    }

    enhanced_edges = []
    flesh_ids = set()

    for rel_type, (filename, freq_threshold) in co_occur_configs.items():
        file_path = os.path.join(rel_dir, filename)
        if not os.path.exists(file_path):
            continue

        print(f"--- 正在从 {filename} 提取 [{rel_type}] 软相关边 ---")
        entity_to_concepts = {}
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    c_id, e_id = parts[0], parts[1]
                    if c_id in all_target_concepts:
                        if e_id not in entity_to_concepts:
                            entity_to_concepts[e_id] = []
                        entity_to_concepts[e_id].append(c_id)

        pair_counts = Counter()
        for e_id, c_list in entity_to_concepts.items():
            active_list = sorted(list(set(c_list)))
            if len(active_list) < 2:
                continue
            for i in range(len(active_list)):
                for j in range(i + 1, len(active_list)):
                    pair = (active_list[i], active_list[j])
                    pair_counts[pair] += 1

        count = 0
        for (id1, id2), freq in pair_counts.items():
            if freq >= freq_threshold:
                if id1 in backbone_ids or id2 in backbone_ids:
                    # 语义修复：共现关系本质是对称的，恢复双向添加以增强 HGT 的消息传递
                    # 这虽然会让整图含环，但符合异构图表征学习的初衷
                    enhanced_edges.append(
                        {"source": id1, "target": id2, "relation": rel_type}
                    )
                    enhanced_edges.append(
                        {"source": id2, "target": id1, "relation": rel_type}
                    )

                    if id1 not in backbone_ids:
                        flesh_ids.add(id1)
                    if id2 not in backbone_ids:
                        flesh_ids.add(id2)
                    count += 2
        print(f"  - 已添加 {count} 条对称 [{rel_type}] 边 (增强语义表征)")

    # 5. 规范化先修关系 (去重)
    # 移除原先基于 LLM Level 和 ID 字典序的翻转逻辑，因为：
    # 1. 人工确认的先修边（ground_truth）不应被带有噪声的 LLM 定级推翻。
    # 2. 缺失 level 时按 ID 排序会强行构造不真实的依赖。
    print("--- 正在规范化先修边 (仅去重，不翻转) ---")

    unique_prereqs = {}  # (src, tgt) -> edge_data
    original_count = len(prereq_edges)

    for edge in prereq_edges:
        u, v = edge["source"], edge["target"]

        # 使用字典进行去重 (保留人工标注的原始方向)
        if (u, v) not in unique_prereqs:
            unique_prereqs[(u, v)] = {
                "source": u,
                "target": v,
                "relation": "prerequisite",
            }

    prereq_edges = list(unique_prereqs.values())
    merged_count = original_count - len(prereq_edges)

    print(f"  - 先修边处理完成: 合并(去重) {merged_count} 条")
    print(f"  - 最终保留了 {len(prereq_edges)} 条唯一的先修逻辑连接")

    # 6. 组装节点列表
    final_nodes = []
    all_active_ids = sorted(list(backbone_ids | flesh_ids))
    for c_id in all_active_ids:
        name = all_target_concepts[c_id]
        short_type = cat_map.get(c_id, "T")
        full_type = {"T": "Theory", "M": "Method", "A": "Application", "O": "Tool"}.get(
            short_type, "Theory"
        )
        is_backbone = 1 if c_id in backbone_ids else 0
        level = level_map.get(c_id, 5)
        final_nodes.append(
            {
                "id": c_id,
                "name": name,
                "type": full_type,
                "is_backbone": is_backbone,
                "level": level,
            }
        )

    print(
        f"  - 最终规模: Backbone {len(backbone_ids)}, Flesh {len(flesh_ids)}, 总边数 {len(prereq_edges) + len(enhanced_edges)}"
    )

    # 对边进行排序，保证图结构的物理存储顺序也是确定的
    all_edges = sorted(
        prereq_edges + enhanced_edges,
        key=lambda x: (x["source"], x["target"], x["relation"]),
    )

    kg_data = {"nodes": final_nodes, "edges": all_edges}
    return kg_data, {"field": target_field}
