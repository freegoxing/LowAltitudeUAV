import json
import requests
import time
import os
import sys
import argparse
from typing import List, Dict, Any

# 自动将项目根目录添加到 sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from hgt_rl_planner.data_loader import extract_concept_dict_by_field

# ================= 配置区 =================
OLLAMA_HOST = "localhost" 
OLLAMA_PORT = "11434"
MODEL_NAME = "qwen3:32b"
MOOCCUBEX_DATA_DIR = "data/MOOCCubex"
BATCH_SIZE = 30
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"

# 不同领域的提示词模板
FIELD_PROMPTS = {
    "心理学": """
Role: 心理学领域专家。
Task: 将以下概念按心理学知识图谱中的主类型分类。

Categories:
T (Theory): 基础理论、概念、心理机制、认知模型、经典理论框架、学科分支。
M (Method): 研究方法、实验范式、测量方法、统计分析方法、研究设计、数据处理方法。
A (Application): 心理学在真实场景中的应用方向、干预实践、应用领域、问题场景。
O (Tool): 可直接使用的具体工具、量表、软件、平台、设备、仪器。

Decision Rules:
- 优先按“概念在课程中的主要角色”分类，只选 1 类。
- 只有当概念明显是具体工具或具体量表/软件/设备时，才标为 O。
- 学科分支、理论流派、抽象概念、心理机制，不要标为 O。
- “实验设计”“统计方法”“问卷法”这类方法论内容优先标为 M，而不是 O。
- “临床心理学”“教育心理学”“用户体验设计中的心理学应用”这类应用方向优先标为 A。
- 无法确定时，优先级按 T > M > A > O 处理，避免滥用 O。

待分类列表 (格式为 ID: Name): {concepts}

Constraint:
- 严禁输出任何解释性文字。
- 必须且仅返回一个标准 JSON 对象，键为概念的 ID，值为分类缩写 (T, M, A, O)。
- 不要包含 Markdown 代码块标签。
""",
    "计算机科学与技术": """
Role: 计算机科学与技术领域专家。
Task: 将以下概念按计算机科学知识图谱中的主类型分类。

Categories:
T (Theory): 计算机科学基础理论、数学基础、计算理论、算法原理、体系结构基础概念。
M (Method): 开发方法论、架构设计方法、算法实现逻辑、软件工程流程、通信协议、技术标准。
A (Application): 计算机技术在各行业的应用场景、业务逻辑、复杂系统解决方案、工程实践。
O (Tool): 编程语言、开发工具链、编译器、第三方库/框架、操作系统、云平台、硬件设备。

Decision Rules:
- “Java”“Python”“Linux”等具体实现应标为 O。
- “时间复杂度”“图论”“自动机”等理论基石应标为 T。
- “敏捷开发”“设计模式”“HTTP协议”“排序算法”等方法论和规范应标为 M。
- “人工智能应用”“电子商务系统”“自动驾驶”等应用领域应标为 A。
- 无法确定时，优先级按 T > M > A > O 处理。

待分类列表 (格式为 ID: Name): {concepts}

Constraint:
- 严禁输出任何解释性文字。
- 必须且仅返回一个标准 JSON 对象，键为概念的 ID，值为分类缩写 (T, M, A, O)。
- 不要包含 Markdown 代码块标签。
"""
}

def call_ollama(concepts: List[str], prompt_template: str) -> Dict[str, str]:
    """调用远程 Ollama API"""
    prompt = prompt_template.format(concepts=", ".join(concepts))
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
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
        print(f"\n[Error] 调用 LLM 失败: {e}")
        return {}

def main():
    parser = argparse.ArgumentParser(description="根据领域对概念进行分类")
    parser.add_argument("--field", type=str, default="心理学", help="目标领域 (默认: 心理学)")
    args = parser.parse_args()

    target_field = args.field
    if target_field not in FIELD_PROMPTS:
        print(f"警告: 领域 '{target_field}' 暂无专用提示词，将使用心理学模板兜底。")
        prompt_template = FIELD_PROMPTS["心理学"]
    else:
        prompt_template = FIELD_PROMPTS[target_field]

    output_file = f"data/MOOCCubex/concept_categories_{target_field}.json"
    print(f">>> 开始处理领域: {target_field}")
    print(f">>> 输出文件: {output_file}")

    # 1. 提取原始概念字典
    try:
        all_concepts_dict = extract_concept_dict_by_field(MOOCCUBEX_DATA_DIR, target_field)
        all_concepts = list(all_concepts_dict.keys())
        print(f"提取完成，共 {len(all_concepts)} 个唯一概念。")
    except Exception as e:
        print(f"数据提取失败: {e}")
        return

    # 2. 加载进度
    classified_data = {}
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            try:
                loaded_data = json.load(f)
                valid_types = {"T", "M", "A", "O"}
                classified_data = {
                    k: v for k, v in loaded_data.items()
                    if k in all_concepts and v in valid_types
                }
                print(f"已加载现有进度: {len(classified_data)} 条已分类。")
            except:
                print("进度文件损坏，重新开始。")

    remaining = [c for c in all_concepts if c not in classified_data]
    if not remaining:
        print("所有概念已全部分类完毕！")
        return

    # 3. 分批处理
    total_initial_remaining = len(remaining)
    consecutive_failures = 0
    
    try:
        while remaining:
            batch_ids = remaining[:BATCH_SIZE]
            batch_prompt_data = [f"{cid}: {all_concepts_dict[cid]}" for cid in batch_ids]
            
            processed_count = total_initial_remaining - len(remaining)
            print(f"\r进度: {processed_count + len(batch_ids)}/{total_initial_remaining} ", end="", flush=True)
            
            success_in_batch = []
            for retry in range(3):
                result = call_ollama(batch_prompt_data, prompt_template)
                if result:
                    valid_result = {k: v for k, v in result.items() if k in batch_ids and v in {"T", "M", "A", "O"}}
                    if valid_result:
                        success_in_batch.extend(list(valid_result.keys()))
                        classified_data.update(valid_result)
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(classified_data, f, ensure_ascii=False, indent=2)
                        if len(valid_result) >= len(batch_ids):
                            break
                time.sleep(1)
            
            if success_in_batch:
                success_set = set(success_in_batch)
                remaining = [c for c in remaining if c not in success_set]
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                remaining = remaining[BATCH_SIZE:] + batch_ids # 移到队尾
                if consecutive_failures >= 5:
                    print("\n[错误] 连续失败多次，停止。")
                    break
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[Stop] 用户手动停止。")

if __name__ == "__main__":
    main()
