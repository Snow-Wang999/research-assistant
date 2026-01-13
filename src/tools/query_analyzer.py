"""查询分析器 - 理解用户意图并生成多组搜索关键词"""
import httpx
import json
import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class QueryAnalysis:
    """查询分析结果"""
    original_query: str           # 原始查询
    intent: str                   # 用户意图描述
    keywords: list[str]           # 多组搜索关键词
    suggested_mode: str           # 建议模式: "simple" | "deep_research"


class QueryAnalyzer:
    """
    查询分析器

    将用户查询转换为：
    1. 意图理解
    2. 多组英文搜索关键词（3-5组）
    3. 搜索模式建议
    """

    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

    SYSTEM_PROMPT = """你是一个学术搜索助手。分析用户的研究问题，生成适合学术论文搜索的关键词。

任务：
1. 理解用户想要研究什么
2. 生成 3-5 组不同角度的英文搜索关键词
3. 判断是简单查询还是需要深度研究

输出 JSON 格式（不要输出其他内容）：
{
  "intent": "用户意图的简短描述（中文，20字内）",
  "keywords": [
    "keyword group 1",
    "keyword group 2",
    "keyword group 3"
  ],
  "suggested_mode": "simple 或 deep_research"
}

关键词生成规则：
- 每组关键词 2-5 个英文词，空格分隔
- 保留专业术语原文（如 Transformer, BERT, RAG）
- 从不同角度生成：核心概念、应用场景、相关技术、最新方法
- 不要加引号

模式判断规则：
- simple: 了解概念、查找论文、单一主题
- deep_research: 对比分析、综述、趋势、多主题关联

示例：
输入: "RAG在文档解析任务中的作用"
输出:
{
  "intent": "了解RAG在文档解析中的应用",
  "keywords": [
    "RAG document parsing",
    "retrieval augmented generation PDF",
    "LLM document understanding RAG",
    "RAG information extraction"
  ],
  "suggested_mode": "simple"
}

输入: "对比Transformer和Mamba在长序列建模上的优劣"
输出:
{
  "intent": "对比Transformer和Mamba处理长序列的能力",
  "keywords": [
    "Transformer Mamba comparison",
    "Mamba state space model long sequence",
    "Transformer attention long context",
    "Mamba vs Transformer efficiency"
  ],
  "suggested_mode": "deep_research"
}"""

    def __init__(self, deepseek_api_key: Optional[str] = None):
        self.api_key = deepseek_api_key

    def _contains_chinese(self, text: str) -> bool:
        """检查文本是否包含中文"""
        return bool(re.search(r'[\u4e00-\u9fff]', text))

    def _parse_response(self, content: str) -> dict:
        """解析 LLM 响应的 JSON"""
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 块
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # 解析失败，返回默认结构
        return None

    def analyze(self, query: str) -> QueryAnalysis:
        """
        分析用户查询

        Args:
            query: 用户查询

        Returns:
            QueryAnalysis 包含意图、关键词、建议模式
        """
        # 如果没有 API key，使用简单回退
        if not self.api_key:
            return self._fallback_analyze(query)

        try:
            response = httpx.post(
                self.DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": query}
                    ],
                    "max_tokens": 300,
                    "temperature": 0.3
                },
                timeout=30.0
            )
            response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"]
            parsed = self._parse_response(content)

            if parsed and "keywords" in parsed:
                result = QueryAnalysis(
                    original_query=query,
                    intent=parsed.get("intent", ""),
                    keywords=parsed.get("keywords", [query]),
                    suggested_mode=parsed.get("suggested_mode", "simple")
                )
                print(f"[QueryAnalyzer] 意图: {result.intent}")
                print(f"[QueryAnalyzer] 关键词: {result.keywords}")
                print(f"[QueryAnalyzer] 建议模式: {result.suggested_mode}")
                return result
            else:
                return self._fallback_analyze(query)

        except Exception as e:
            print(f"[QueryAnalyzer] 分析出错: {e}")
            return self._fallback_analyze(query)

    def _fallback_analyze(self, query: str) -> QueryAnalysis:
        """回退方案：简单处理"""
        # 提取英文词作为关键词
        english_words = re.findall(r'[a-zA-Z][a-zA-Z0-9]*', query)

        if english_words:
            keywords = [' '.join(english_words)]
        else:
            keywords = [query]

        # 简单规则判断模式
        complex_keywords = ["对比", "比较", "综述", "趋势", "分析", "优劣"]
        suggested_mode = "simple"
        for kw in complex_keywords:
            if kw in query:
                suggested_mode = "deep_research"
                break

        return QueryAnalysis(
            original_query=query,
            intent="",
            keywords=keywords,
            suggested_mode=suggested_mode
        )


# 测试代码
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    analyzer = QueryAnalyzer(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY")
    )

    test_queries = [
        "RAG在文档解析任务中的作用",
        "Transformer是什么",
        "对比Transformer和Mamba在长序列建模上的优劣",
        "大模型最新进展",
        "BERT的预训练方法",
    ]

    print("=" * 60)
    print("QueryAnalyzer 测试")
    print("=" * 60)

    for query in test_queries:
        print(f"\n查询: {query}")
        print("-" * 40)
        result = analyzer.analyze(query)
        print(f"意图: {result.intent}")
        print(f"关键词: {result.keywords}")
        print(f"建议模式: {result.suggested_mode}")
