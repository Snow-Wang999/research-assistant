"""统一 LLM 客户端

支持通义千问 API，针对不同任务使用不同规模的模型。
"""
import os
import httpx
from typing import Optional, Literal

from .logger import get_llm_logger

log = get_llm_logger()

TaskType = Literal["intent", "screen", "compress", "report"]
ModelSize = Literal["turbo", "plus", "max"]


class QwenClient:
    """
    通义千问 API 客户端

    自动根据任务类型选择合适的模型：
    - intent/screen: qwen-turbo (快速、便宜)
    - compress: qwen-plus (平衡)
    - report: qwen-plus (平衡)
    """

    # API 配置
    API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    # 模型定义
    MODELS = {
        "turbo": "qwen-turbo",
        "plus": "qwen-plus",
        "max": "qwen-max"
    }

    # 任务到模型的映射
    TASK_MODEL_MAP: dict[TaskType, ModelSize] = {
        "intent": "turbo",      # 意图识别 - 小模型
        "screen": "turbo",      # 论文筛选 - 小模型
        "compress": "plus",     # 内容压缩 - 中模型
        "report": "plus"        # 报告生成 - 中模型
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化客户端

        Args:
            api_key: 通义千问 API Key（默认从环境变量 QWEN_API_KEY 读取）
        """
        self.api_key = api_key or os.getenv("QWEN_API_KEY")
        if not self.api_key:
            raise ValueError(
                "缺少 QWEN_API_KEY。请在 .env 文件中配置或传入 api_key 参数。"
            )

    def chat(
        self,
        prompt: str,
        task_type: TaskType,
        max_tokens: int = 2000,
        temperature: float = 0.3,
        timeout: float = 30.0,
        model_override: Optional[ModelSize] = None
    ) -> str:
        """
        调用通义千问 API

        Args:
            prompt: 用户提示词
            task_type: 任务类型（自动选择模型）
            max_tokens: 最大生成 token 数
            temperature: 温度参数
            timeout: 超时时间（秒）
            model_override: 强制使用指定模型（覆盖自动选择）

        Returns:
            str: LLM 响应内容

        Raises:
            Exception: API 调用失败
        """
        # 选择模型
        model_size = model_override or self.TASK_MODEL_MAP[task_type]
        model_name = self.MODELS[model_size]

        log.info(f"任务: {task_type}, 使用模型: {model_name}")
        log.debug(f"Prompt 长度: {len(prompt)} 字符, max_tokens: {max_tokens}")

        # 调用 API
        try:
            response = httpx.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                },
                timeout=timeout
            )
            response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"]
            log.info(f"响应成功, 长度: {len(content)} 字符")
            log.debug(f"响应预览: {content[:200]}..." if len(content) > 200 else f"响应: {content}")
            return content
        except httpx.TimeoutException as e:
            log.error(f"API 调用超时: {timeout}秒")
            raise
        except httpx.HTTPStatusError as e:
            log.error(f"API 返回错误: {e.response.status_code} - {e.response.text[:200]}")
            raise
        except Exception as e:
            log.error(f"API 调用异常: {type(e).__name__}: {str(e)}")
            raise


# 便捷函数
def get_qwen_client(api_key: Optional[str] = None) -> QwenClient:
    """
    获取通义千问客户端实例

    Args:
        api_key: API Key（可选）

    Returns:
        QwenClient: 客户端实例
    """
    return QwenClient(api_key=api_key)


# 测试代码
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    client = QwenClient()

    # 测试意图识别（使用 turbo）
    print("\n=== 测试意图识别（qwen-turbo）===")
    response = client.chat(
        prompt="判断这个查询是简单查询还是复杂查询：什么是 Transformer？",
        task_type="intent",
        max_tokens=100
    )
    print(f"响应: {response}")

    # 测试压缩（使用 plus）
    print("\n=== 测试压缩（qwen-plus）===")
    response = client.chat(
        prompt="用一句话总结：Transformer 是一种基于注意力机制的神经网络架构。",
        task_type="compress",
        max_tokens=50
    )
    print(f"响应: {response}")
