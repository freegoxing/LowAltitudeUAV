import json
import os
import re

from .ollama_client import OllamaClient


class SituationAssessor:
    """
    真实版 Agent 1：态势评估与任务分级
    利用 Ollama 加载本地模型，并读取 `agent1_skill.md` 作为系统提示词。
    """

    def __init__(self, skill_path: str = None, client: OllamaClient = None):
        if skill_path is None:
            # 默认指向同目录下的 agent1_skill.md
            skill_path = os.path.join(os.path.dirname(__file__), "agent1_skill.md")

        self.skill_path = skill_path
        self.client = client or OllamaClient()
        self._load_skill()

    def _load_skill(self):
        """加载 SkillOpt 的 Markdown 文档作为 System Prompt"""
        try:
            with open(self.skill_path, encoding="utf-8") as f:
                content = f.read()

            # 去除 YAML frontmatter 以防止干扰 LLM
            # frontmatter 格式为 --- \n ... \n ---
            content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)
            self.system_prompt = content.strip()
        except FileNotFoundError:
            print(f"[Error] 找不到技能文档: {self.skill_path}")
            self.system_prompt = "你是一个态势评估智能体。请输出 { 'urgency': 3, 'feasibility': 3, 'level': 'Level_2', 'report': '默认' }"

    def assess_situation(
        self, graph_stats: dict, env_info: dict, target_info: dict
    ) -> dict:
        """
        输入网络统计数据、环境信息和目标信息，调用 LLM 返回评估结果。
        """
        # 构建给用户的输入 Prompt
        user_prompt = json.dumps(
            {
                "graph_stats": graph_stats,
                "env_info": env_info,
                "target_info": target_info,
            },
            ensure_ascii=False,
            indent=2,
        )

        print("\n[🤖 Agent 1 真实评估中 (Powered by Ollama)...]")
        print(f"  > 输入态势特征: {user_prompt}")

        response_text = self.client.chat(self.system_prompt, user_prompt)

        if not response_text:
            return self._fallback_response()

        return self._parse_json_response(response_text)

    def _parse_json_response(self, text: str) -> dict:
        """从 LLM 响应中提取 JSON"""
        try:
            # 尝试直接解析
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试用正则提取 Markdown 代码块中的 JSON
            match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
            print(f"[Error] LLM 返回了无法解析的格式: {text}")
            return self._fallback_response()

    def _fallback_response(self) -> dict:
        return {
            "urgency": 3,
            "feasibility": 3,
            "level": "Level_2",
            "report": "Fallback default assessment due to LLM error.",
        }
