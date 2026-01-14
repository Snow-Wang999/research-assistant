"""子问题分解器

将复杂的研究问题分解为多个可独立研究的子问题。
参考 Open Deep Research 的 Supervisor 设计。
"""
import json
import re
from typing import List, Optional
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.llm_client import QwenClient


@dataclass
class SubQuestion:
    """子问题"""
    question: str       # 子问题内容
    purpose: str        # 研究目的
    search_keywords: List[str]  # 建议的搜索关键词


@dataclass
class DecompositionResult:
    """分解结果"""
    original_query: str          # 原始查询
    query_type: str              # 查询类型
    sub_questions: List[SubQuestion]  # 子问题列表
    research_strategy: str       # 研究策略说明


class SubQuestionDecomposer:
    """
    子问题分解器

    使用 LLM 将复杂问题分解为多个子问题，
    每个子问题可以独立进行搜索研究。
    """

    SYSTEM_PROMPT = """你是一个研究问题分析专家。你的任务是将复杂的研究问题分解为多个可独立研究的子问题。

任务：分析用户的研究问题，识别问题类型，并分解为3-5个子问题。

问题类型判断：
- comparison: 对比分析（如"A和B有什么区别"）
- overview: 综述概览（如"某领域的发展现状"）
- trend: 趋势分析（如"某技术的发展趋势"）
- deep_dive: 深入研究（如"某方法的原理和应用"）

分解原则：
1. 每个子问题应该可以独立搜索研究
2. 子问题之间应该互补，共同覆盖原问题
3. 对比类问题：为每个对比对象创建独立子问题，再加一个综合对比子问题
4. 综述类问题：按时间/主题/应用场景分解
5. 趋势类问题：按历史/现状/未来分解

**搜索关键词优化策略**（非常重要）：
1. 使用学术术语而非通俗说法（如 "recurrent neural network" 而非 "循环网络"）
2. 对比类问题：必须包含 "comparison"、"vs"、"versus" 等词
3. 综述类问题：必须包含 "survey"、"review"、"overview" 等词
4. 每组关键词2-4个词，太长会降低搜索效果
5. 包含核心技术名称的精确拼写（如 "Transformer", "LSTM", "attention"）
6. 可以加入 "benchmark"、"evaluation" 来找对比实验论文

输出 JSON 格式（不要输出其他内容）：
{
  "query_type": "comparison|overview|trend|deep_dive",
  "research_strategy": "研究策略简述（30字内）",
  "sub_questions": [
    {
      "question": "子问题描述",
      "purpose": "这个子问题的研究目的（15字内）",
      "search_keywords": ["关键词1", "关键词2", "关键词3"]
    }
  ]
}

示例：
用户问题："对比 Transformer 和 RNN 在 NLP 中的应用"

输出：
{
  "query_type": "comparison",
  "research_strategy": "分别研究两种架构，再进行综合对比",
  "sub_questions": [
    {
      "question": "Transformer 架构的核心原理和在 NLP 中的典型应用",
      "purpose": "了解 Transformer 基础",
      "search_keywords": ["Transformer architecture NLP", "self-attention mechanism", "Transformer survey"]
    },
    {
      "question": "RNN/LSTM 架构的核心原理和在 NLP 中的典型应用",
      "purpose": "了解 RNN 基础",
      "search_keywords": ["LSTM recurrent neural network", "RNN sequence modeling", "RNN NLP review"]
    },
    {
      "question": "Transformer 与 RNN 在性能、效率、适用场景上的对比",
      "purpose": "综合对比分析",
      "search_keywords": ["Transformer vs RNN comparison", "attention versus recurrence benchmark", "sequence model evaluation"]
    }
  ]
}"""

    def __init__(self, qwen_api_key: Optional[str] = None):
        """
        初始化分解器

        Args:
            qwen_api_key: 通义千问 API Key
        """
        self.llm_client = QwenClient(api_key=qwen_api_key) if qwen_api_key else None

    def decompose(self, query: str) -> DecompositionResult:
        """
        分解复杂问题为子问题

        Args:
            query: 用户的研究问题

        Returns:
            DecompositionResult: 分解结果
        """
        if not self.llm_client:
            return self._fallback_decompose(query)

        try:
            # 使用通义千问 turbo 模型（问题分解是简单任务）
            prompt = f"{self.SYSTEM_PROMPT}\n\n研究问题：{query}"
            content = self.llm_client.chat(
                prompt=prompt,
                task_type="intent",
                max_tokens=1000,
                temperature=0.3,
                timeout=15.0
            )

            parsed = self._parse_response(content)

            if parsed:
                return self._format_result(query, parsed)
            else:
                return self._fallback_decompose(query)

        except Exception as e:
            print(f"[Decomposer] 分解出错: {e}")
            return self._fallback_decompose(query)

    def _parse_response(self, content: str) -> Optional[dict]:
        """解析 LLM 响应"""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _format_result(self, query: str, parsed: dict) -> DecompositionResult:
        """格式化解析结果"""
        sub_questions = []
        for sq in parsed.get("sub_questions", []):
            sub_questions.append(SubQuestion(
                question=sq.get("question", ""),
                purpose=sq.get("purpose", ""),
                search_keywords=sq.get("search_keywords", [])
            ))

        return DecompositionResult(
            original_query=query,
            query_type=parsed.get("query_type", "deep_dive"),
            sub_questions=sub_questions,
            research_strategy=parsed.get("research_strategy", "")
        )

    def _fallback_decompose(self, query: str) -> DecompositionResult:
        """
        回退方案：基于规则的简单分解
        """
        # 检测对比类问题
        comparison_patterns = ["对比", "比较", "区别", "差异", "vs", "VS", "和", "与"]
        is_comparison = any(p in query for p in comparison_patterns)

        if is_comparison:
            # 尝试提取对比对象
            sub_questions = [
                SubQuestion(
                    question=f"{query} - 第一个对象的核心特点",
                    purpose="了解第一个对象",
                    search_keywords=[query]
                ),
                SubQuestion(
                    question=f"{query} - 第二个对象的核心特点",
                    purpose="了解第二个对象",
                    search_keywords=[query]
                ),
                SubQuestion(
                    question=f"{query} - 综合对比分析",
                    purpose="综合对比",
                    search_keywords=[query, "comparison"]
                )
            ]
            query_type = "comparison"
            strategy = "分别研究各对象，再综合对比"
        else:
            # 通用分解
            sub_questions = [
                SubQuestion(
                    question=f"{query} - 基础概念和原理",
                    purpose="了解基础知识",
                    search_keywords=[query, "introduction", "基础"]
                ),
                SubQuestion(
                    question=f"{query} - 最新研究进展",
                    purpose="了解前沿动态",
                    search_keywords=[query, "recent", "2024", "最新"]
                ),
                SubQuestion(
                    question=f"{query} - 应用场景和案例",
                    purpose="了解实际应用",
                    search_keywords=[query, "application", "应用"]
                )
            ]
            query_type = "deep_dive"
            strategy = "从基础到前沿，再到应用"

        return DecompositionResult(
            original_query=query,
            query_type=query_type,
            sub_questions=sub_questions,
            research_strategy=strategy
        )


# 测试代码
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    decomposer = SubQuestionDecomposer(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY")
    )

    test_queries = [
        "对比 Transformer 和 CNN 在计算机视觉中的应用",
        "大语言模型的发展趋势和未来方向",
        "强化学习在机器人控制中的应用"
    ]

    for query in test_queries:
        print("=" * 60)
        print(f"原始问题: {query}")
        print("-" * 60)

        result = decomposer.decompose(query)

        print(f"问题类型: {result.query_type}")
        print(f"研究策略: {result.research_strategy}")
        print(f"\n子问题列表:")

        for i, sq in enumerate(result.sub_questions, 1):
            print(f"\n  [{i}] {sq.question}")
            print(f"      目的: {sq.purpose}")
            print(f"      关键词: {sq.search_keywords}")
        print()
