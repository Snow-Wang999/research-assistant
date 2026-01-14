"""查询翻译器 - 将中文查询翻译为英文搜索关键词"""
import httpx
import re
from typing import Optional


class QueryTranslator:
    """
    查询翻译器

    使用 LLM 将中文查询翻译为适合学术搜索的英文关键词。
    支持 DeepSeek API（兼容 OpenAI 格式）。
    """

    # DeepSeek API 端点
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

    # 通义千问 API 端点
    QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    def __init__(
        self,
        deepseek_api_key: Optional[str] = None,
        qwen_api_key: Optional[str] = None,
        provider: str = "qwen"  # "deepseek" 或 "qwen"，默认使用 qwen
    ):
        """
        初始化翻译器

        Args:
            deepseek_api_key: DeepSeek API Key
            qwen_api_key: 通义千问 API Key
            provider: 使用的 LLM 提供商
        """
        self.deepseek_api_key = deepseek_api_key
        self.qwen_api_key = qwen_api_key
        self.provider = provider

    def _get_api_config(self) -> tuple[str, str, str]:
        """获取当前提供商的 API 配置"""
        if self.provider == "deepseek" and self.deepseek_api_key:
            return self.DEEPSEEK_API_URL, self.deepseek_api_key, "deepseek-chat"
        elif self.provider == "qwen" and self.qwen_api_key:
            return self.QWEN_API_URL, self.qwen_api_key, "qwen-turbo"
        elif self.deepseek_api_key:
            return self.DEEPSEEK_API_URL, self.deepseek_api_key, "deepseek-chat"
        elif self.qwen_api_key:
            return self.QWEN_API_URL, self.qwen_api_key, "qwen-turbo"
        else:
            raise ValueError("未配置任何 LLM API Key")

    def _contains_chinese(self, text: str) -> bool:
        """检查文本是否包含中文"""
        return bool(re.search(r'[\u4e00-\u9fff]', text))

    def _extract_english_keywords(self, text: str) -> str:
        """从文本中提取英文关键词（备用方案）"""
        # 提取所有英文单词
        english_words = re.findall(r'[a-zA-Z]+', text)
        if english_words:
            return ' '.join(english_words)
        return text

    def translate(self, query: str) -> str:
        """
        翻译查询

        如果查询包含中文，则翻译为英文搜索关键词。
        如果查询已经是英文，则直接返回。

        Args:
            query: 用户查询

        Returns:
            英文搜索关键词
        """
        # 如果不包含中文，直接返回
        if not self._contains_chinese(query):
            return query

        try:
            api_url, api_key, model = self._get_api_config()

            response = httpx.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": """你是一个学术搜索助手。将用户的中文查询翻译为适合在学术论文数据库（如arXiv、Google Scholar）中搜索的英文关键词。

规则：
1. 只输出英文关键词，不要输出其他内容
2. 保留专业术语的英文原词（如 Transformer、BERT、GPT）
3. 提取核心概念，去掉语气词和无关词汇
4. 用空格分隔关键词
5. 不要加引号或其他标点

示例：
- "Transformer是什么" → "Transformer architecture attention mechanism"
- "对比Transformer和Mamba的优劣" → "Transformer Mamba comparison state space model"
- "大模型最新进展" → "large language model LLM recent advances"
"""
                        },
                        {
                            "role": "user",
                            "content": query
                        }
                    ],
                    "max_tokens": 100,
                    "temperature": 0.1
                },
                timeout=30.0
            )
            response.raise_for_status()

            result = response.json()
            translated = result["choices"][0]["message"]["content"].strip()

            # 清理结果（去掉可能的引号等）
            translated = translated.strip('"\'')

            print(f"[翻译] {query} → {translated}")
            return translated

        except Exception as e:
            print(f"翻译出错: {e}")
            # 降级：尝试提取英文关键词
            fallback = self._extract_english_keywords(query)
            if fallback != query:
                print(f"[降级] 使用提取的英文关键词: {fallback}")
                return fallback
            return query


# 测试代码
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    translator = QueryTranslator(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        qwen_api_key=os.getenv("QWEN_API_KEY")
    )

    test_queries = [
        "Transformer是什么",
        "对比Transformer和Mamba的优劣",
        "大模型领域最新的研究进展有哪些",
        "BERT的作者是谁",
        "What is attention mechanism",  # 纯英文
    ]

    print("=" * 60)
    print("查询翻译测试")
    print("=" * 60)

    for query in test_queries:
        translated = translator.translate(query)
        print(f"\n原始: {query}")
        print(f"翻译: {translated}")
