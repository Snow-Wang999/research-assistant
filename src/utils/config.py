"""项目配置"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    """项目配置"""

    # API Keys - LLM
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")

    # API Keys - 搜索服务
    SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

    # 模型配置
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "claude-sonnet-4-20250514")

    # 翻译配置
    TRANSLATOR_PROVIDER = os.getenv("TRANSLATOR_PROVIDER", "deepseek")  # deepseek 或 qwen

    # 路径配置
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    LOGS_DIR = PROJECT_ROOT / "logs"

    # 搜索配置
    DEFAULT_SEARCH_LIMIT = int(os.getenv("DEFAULT_SEARCH_LIMIT", "10"))

    @classmethod
    def validate(cls):
        """验证必要配置"""
        # 检查是否有可用的 LLM API Key
        if not any([cls.ANTHROPIC_API_KEY, cls.OPENAI_API_KEY,
                    cls.DEEPSEEK_API_KEY, cls.QWEN_API_KEY]):
            print("警告: 未配置任何 LLM API Key，查询翻译功能将不可用")

    @classmethod
    def get_translator_config(cls) -> dict:
        """获取翻译器配置"""
        return {
            "deepseek_api_key": cls.DEEPSEEK_API_KEY,
            "qwen_api_key": cls.QWEN_API_KEY,
            "provider": cls.TRANSLATOR_PROVIDER
        }

config = Config()
