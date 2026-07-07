import json
import requests
import time
import os
import sys
import argparse
from typing import List, Dict, Any

# 自动处理路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from hgt_rl_planner.data_loader import extract_concept_dict_by_field

# ================= 配置区 =================
OLLAMA_HOST = "localhost" 
OLLAMA_PORT = "11434"
MODEL_NAME = "qwen3:32b"
DATA_DIR = "data/MOOCCubex"
BATCH_SIZE = 20
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"

FIELD_RANK_PROMPTS = {
    "心理学": """
Role: 心理学教育专家、教材编纂者。
Task: 评估以下心理学概念在学习路径中的“学习层级等级”。

Level Definition (1-10):
1-2: 入门起点。零基础即可接触，是大量后续内容的前提。
3-4: 本科早期核心基础。理解多数心理学课程前应先掌握。
5-6: 本科中后期进阶。需要若干基础理论、方法或统计知识。
7-8: 高级专题。通常需要较完整的本科基础或较强方法背景。
9-10: 高度专门化或研究级主题。

Scoring Principle:
- 评分优先依据教学先修顺序、抽象程度、所需背景知识。
- 更基础、更通用、更常作为其他概念前提的概念，应给更低分。

待评估列表 (格式为 ID: Name): {concepts}

Constraint:
1. 严禁解释。
2. 必须返回标准 JSON 对象，键为概念的 ID，值为 1-10 的整数。
3. 不要包含 Markdown 代码块标签。
""",
    "计算机科学与技术": """
Role: 计算机科学教育专家、课程体系设计者。
Task: 评估以下计算机科学概念在学习路径中的“学习层级等级”。

Level Definition (1-10):
1-2: 入门阶段。基础语法、计算机常识、简单办公软件使用。
3-4: 核心基础。计算机专业本科低年级必修（如：数据结构初阶、C语言、离散数学）。
5-6: 进阶技术。涉及系统底层、软件工程方法或核心架构（如：操作系统、数据库原理、网络协议）。
7-8: 高级专题。通常需要深厚理论基础或复合背景（如：高级算法分析、分布式系统、机器学习数学原理）。
9-10: 高度专门化或前沿研究主题（如：量子计算、计算复杂性理论、密码学前沿）。

Scoring Principle:
- 基础编程工具和常识为低分，底层原理和复杂数学模型为高分。
- 考虑先修依赖：例如，“链表”应低于“平衡树”，“逻辑门”应低于“流水线设计”。

待评估列表 (格式为 ID: Name): {concepts}

Constraint:
1. 严禁解释。
2. 必须返回标准 JSON 对象，键为概念的 ID，值为 1-10 的整数。
3. 不要包含 Markdown 代码块标签。
"""
}

def call_ollama(concepts: List[str], prompt_template: str) -> Dict[str, int]:
    prompt = prompt_template.format(concepts=", ".join(concepts))
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=180)
        response.raise_for_status()
        result_text = response.json().get("response", "{}")
        
        start = result_text.find('{')
        end = result_text.rfind('}')
        if start != -1 and end != -1:
            clean_text = result_text[start : end + 1]
        else:
            clean_text = result_text.strip()
            
        return json.loads(clean_text)
    except Exception as e:
        print(f"\n[Error] Ollama 失败: {e}")
        return {}

def main():
    parser = argparse.ArgumentParser(description="评估概念的学习层级等级")
    parser.add_argument("--field", type=str, default="心理学", help="目标领域 (默认: 心理学)")
    args = parser.parse_args()

    target_field = args.field
    prompt_template = FIELD_RANK_PROMPTS.get(target_field, FIELD_RANK_PROMPTS["心理学"])
    output_file = f"data/MOOCCubex/concept_levels_{target_field}.json"

    print(f">>> 开始对领域进行定级: {target_field}")

    # 1. 提取原始概念字典
    try:
        all_concepts_dict = extract_concept_dict_by_field(DATA_DIR, target_field)
        all_concepts = list(all_concepts_dict.keys())
        print(f"提取完成，共 {len(all_concepts)} 个概念。")
    except Exception as e:
        print(f"数据提取失败: {e}")
        return

    # 2. 加载进度
    leveled_data = {}
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            try:
                loaded_data = json.load(f)
                leveled_data = {
                    k: int(float(v)) for k, v in loaded_data.items() 
                    if k in all_concepts and 1 <= int(float(v)) <= 10
                }
                print(f"已加载现有进度: {len(leveled_data)} 条已定级。")
            except Exception as e:
                print(f"进度文件损坏: {e}")

    remaining = [c for c in all_concepts if c not in leveled_data]
    if not remaining:
        print("所有概念已完成定级！")
        return

    # 3. 分批处理
    total_initial = len(remaining)
    try:
        while remaining:
            batch_ids = remaining[:BATCH_SIZE]
            batch_prompt_data = [f"{cid}: {all_concepts_dict[cid]}" for cid in batch_ids]
            
            print(f"\r进度: {total_initial - len(remaining) + len(batch_ids)}/{total_initial} ", end="", flush=True)
            
            success_in_batch = []
            for _ in range(3):
                result = call_ollama(batch_prompt_data, prompt_template)
                if result:
                    valid_result = {
                        k: int(float(v)) for k, v in result.items() 
                        if k in batch_ids and 1 <= int(float(v)) <= 10
                    }
                    if valid_result:
                        success_in_batch.extend(list(valid_result.keys()))
                        leveled_data.update(valid_result)
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(leveled_data, f, ensure_ascii=False, indent=2)
                        if len(valid_result) >= len(batch_ids):
                            break
                time.sleep(1)
            
            if success_in_batch:
                remaining = [c for c in remaining if c not in set(success_in_batch)]
            else:
                remaining = remaining[BATCH_SIZE:] + batch_ids
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n停止。")

if __name__ == "__main__":
    main()
