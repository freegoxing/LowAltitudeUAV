import json
import time
import urllib.error
import urllib.request


class OllamaClient:
    """
    轻量级 Ollama HTTP 客户端，支持重试和超时机制。
    目标是与本地运行的模型（如 qwen3:8b）进行通信。
    """

    def __init__(
        self, base_url: str = "http://localhost:12434", model: str = "qwen3:8b"
    ):
        self.base_url = base_url
        self.model = model
        self.chat_url = f"{self.base_url}/api/chat"

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
        timeout: int = 60,
    ) -> str | None:
        """
        发送聊天请求到 Ollama，支持设置 system_prompt。
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.2  # 保持评估稳定
            },
        }

        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(self.chat_url, data=data, headers=headers)

        # Bypass proxy to avoid 502 Bad Gateway on localhost
        proxy_support = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_support)
        urllib.request.install_opener(opener)

        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    return result["message"]["content"]
            except urllib.error.URLError as e:
                print(
                    f"[OllamaClient] 连接错误: {e}. 正在重试 ({attempt + 1}/{max_retries})..."
                )
                time.sleep(2)
            except Exception as e:
                print(f"[OllamaClient] 发生未知错误: {e}")
                return None

        print("[OllamaClient] 达到最大重试次数，调用失败。")
        return None
