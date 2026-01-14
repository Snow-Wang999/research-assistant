"""论文筛选器

基于摘要筛选相关论文，决定哪些论文值得获取全文。
参考 Elicit 的 Screening 流程设计。
"""

import json
import re
from typing import List, Optional
from dataclasses import dataclass, field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.llm_client import QwenClient


@dataclass
class ScreenedPaper:
    """筛选后的论文"""
    paper_id: str
    title: str
    authors: List[str]
    year: Optional[int]
    abstract: str
    url: str
    source: str
    citation_count: Optional[int]
    # 筛选结果
    relevance_score: int  # 1-5 分
    relevance_reason: str  # 相关原因
    should_get_fulltext: bool  # 是否需要获取全文

    @property
    def arxiv_id(self) -> Optional[str]:
        """提取 arXiv ID（如果是 arXiv 论文）"""
        if self.source == "arxiv":
            # 从 URL 或 paper_id 提取
            match = re.search(r'(\d{4}\.\d{4,5})', self.url or self.paper_id)
            if match:
                return match.group(1)
        return None


@dataclass
class ScreeningResult:
    """筛选结果"""
    query: str
    total_papers: int
    screened_papers: List[ScreenedPaper]
    papers_for_fulltext: List[ScreenedPaper]  # 需要获取全文的论文

    @property
    def fulltext_count(self) -> int:
        return len(self.papers_for_fulltext)


class PaperScreener:
    """
    论文筛选器

    使用 LLM 基于摘要筛选相关论文，决定哪些值得获取全文。
    """

    SCREENING_PROMPT = """你是一个学术论文筛选专家。你的任务是评估每篇论文与研究问题的相关性。

研究问题: {query}

请评估以下论文的相关性。对于每篇论文，请判断：
1. 相关性评分 (1-5分)
2. 是否需要获取全文进行深入分析

评分标准：
- 5分：核心相关，直接讨论研究问题，必须获取全文
- 4分：高度相关，提供重要证据或方法，应该获取全文
- 3分：中等相关，提供背景或部分相关信息，可选获取全文
- 2分：低相关，仅间接涉及，不需要全文
- 1分：不相关，跳过

论文列表：
{papers_text}

请以 JSON 格式输出评估结果：
{{
  "evaluations": [
    {{
      "index": 1,
      "score": 5,
      "reason": "直接对比了 Transformer 和 RNN 的性能",
      "need_fulltext": true
    }},
    {{
      "index": 2,
      "score": 2,
      "reason": "仅提到 Transformer，但主题是图像分类",
      "need_fulltext": false
    }}
  ]
}}

要求：
1. 严格评估相关性，不要放水
2. 只有 score >= 4 的论文才设置 need_fulltext: true
3. 优先选择高引用、近期发表的论文
4. 全文获取数量控制在 {max_fulltext} 篇以内"""

    def __init__(
        self,
        qwen_api_key: Optional[str] = None,
        max_fulltext: int = 15,
        min_score_for_fulltext: int = 4
    ):
        """
        初始化筛选器

        Args:
            qwen_api_key: 通义千问 API Key
            max_fulltext: 最大获取全文的论文数
            min_score_for_fulltext: 获取全文的最低分数
        """
        self.llm_client = QwenClient(api_key=qwen_api_key) if qwen_api_key else None
        self.max_fulltext = max_fulltext
        self.min_score_for_fulltext = min_score_for_fulltext

    def screen(
        self,
        query: str,
        papers: List[dict],
        max_fulltext: Optional[int] = None
    ) -> ScreeningResult:
        """
        筛选论文

        Args:
            query: 研究问题
            papers: 论文列表（需包含 title, abstract, authors, year 等）
            max_fulltext: 最大获取全文数量（覆盖默认值）

        Returns:
            ScreeningResult: 筛选结果
        """
        if not papers:
            return ScreeningResult(
                query=query,
                total_papers=0,
                screened_papers=[],
                papers_for_fulltext=[]
            )

        max_ft = max_fulltext or self.max_fulltext

        if self.llm_client:
            return self._screen_with_llm(query, papers, max_ft)
        else:
            return self._screen_fallback(query, papers, max_ft)

    def _format_papers_for_prompt(self, papers: List[dict]) -> str:
        """格式化论文列表用于 prompt"""
        lines = []
        for i, p in enumerate(papers, 1):
            year = p.get('year', 'N/A')
            citations = p.get('citation_count', 0) or 0
            abstract = (p.get('abstract') or '')[:400]
            source = p.get('source', 'unknown').upper()

            lines.append(
                f"[{i}] {p.get('title', 'Untitled')}\n"
                f"    来源: {source} | 年份: {year} | 引用: {citations}\n"
                f"    摘要: {abstract}..."
            )
        return "\n\n".join(lines)

    def _screen_with_llm(
        self,
        query: str,
        papers: List[dict],
        max_fulltext: int
    ) -> ScreeningResult:
        """使用 LLM 筛选"""
        try:
            papers_text = self._format_papers_for_prompt(papers)

            prompt = self.SCREENING_PROMPT.format(
                query=query,
                papers_text=papers_text,
                max_fulltext=max_fulltext
            )

            print(f"[PaperScreener] 筛选 {len(papers)} 篇论文...")

            # 使用通义千问 turbo 模型（论文筛选是简单分类任务）
            content = self.llm_client.chat(
                prompt=prompt,
                task_type="screen",
                max_tokens=2000,
                temperature=0.2,
                timeout=30.0
            )

            evaluations = self._parse_response(content)

            if evaluations:
                return self._build_result(query, papers, evaluations, max_fulltext)

        except Exception as e:
            print(f"[PaperScreener] LLM 筛选出错: {type(e).__name__}: {e}")

        return self._screen_fallback(query, papers, max_fulltext)

    def _parse_response(self, content: str) -> Optional[List[dict]]:
        """解析 LLM 响应"""
        try:
            data = json.loads(content)
            return data.get("evaluations", [])
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return data.get("evaluations", [])
            except json.JSONDecodeError:
                pass

        return None

    def _build_result(
        self,
        query: str,
        papers: List[dict],
        evaluations: List[dict],
        max_fulltext: int
    ) -> ScreeningResult:
        """构建筛选结果"""
        screened_papers = []

        # 创建评估字典（index -> evaluation）
        eval_dict = {e.get("index", 0): e for e in evaluations}

        for i, paper in enumerate(papers, 1):
            eval_data = eval_dict.get(i, {})
            score = eval_data.get("score", 2)
            reason = eval_data.get("reason", "")
            need_fulltext = eval_data.get("need_fulltext", False)

            screened = ScreenedPaper(
                paper_id=paper.get("paper_id", f"paper_{i}"),
                title=paper.get("title", ""),
                authors=paper.get("authors", []),
                year=paper.get("year"),
                abstract=paper.get("abstract", ""),
                url=paper.get("url", ""),
                source=paper.get("source", "unknown"),
                citation_count=paper.get("citation_count"),
                relevance_score=score,
                relevance_reason=reason,
                should_get_fulltext=need_fulltext and score >= self.min_score_for_fulltext
            )
            screened_papers.append(screened)

        # 按分数排序
        screened_papers.sort(key=lambda x: (-x.relevance_score, -(x.citation_count or 0)))

        # 选择需要获取全文的论文
        papers_for_fulltext = [
            p for p in screened_papers
            if p.should_get_fulltext
        ][:max_fulltext]

        print(f"[PaperScreener] 筛选完成: {len(papers_for_fulltext)}/{len(papers)} 篇需要获取全文")

        return ScreeningResult(
            query=query,
            total_papers=len(papers),
            screened_papers=screened_papers,
            papers_for_fulltext=papers_for_fulltext
        )

    def _screen_fallback(
        self,
        query: str,
        papers: List[dict],
        max_fulltext: int
    ) -> ScreeningResult:
        """回退方案：基于引用数和年份筛选"""
        print("[PaperScreener] 使用回退筛选方案...")

        screened_papers = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for i, paper in enumerate(papers):
            title_lower = (paper.get("title") or "").lower()
            abstract_lower = (paper.get("abstract") or "").lower()

            # 简单相关性评分
            title_match = sum(1 for w in query_words if w in title_lower)
            abstract_match = sum(1 for w in query_words if w in abstract_lower)

            # 引用数加分
            citations = paper.get("citation_count", 0) or 0
            citation_bonus = min(2, citations // 100)

            # 年份加分（近3年）
            year = paper.get("year") or 2020
            year_bonus = 1 if year >= 2022 else 0

            score = min(5, 2 + title_match + (1 if abstract_match > 2 else 0) + citation_bonus + year_bonus)

            screened = ScreenedPaper(
                paper_id=paper.get("paper_id", f"paper_{i}"),
                title=paper.get("title", ""),
                authors=paper.get("authors", []),
                year=paper.get("year"),
                abstract=paper.get("abstract", ""),
                url=paper.get("url", ""),
                source=paper.get("source", "unknown"),
                citation_count=citations,
                relevance_score=score,
                relevance_reason="基于关键词匹配和引用数",
                should_get_fulltext=score >= self.min_score_for_fulltext
            )
            screened_papers.append(screened)

        # 排序
        screened_papers.sort(key=lambda x: (-x.relevance_score, -(x.citation_count or 0)))

        # 选择全文
        papers_for_fulltext = [
            p for p in screened_papers
            if p.should_get_fulltext
        ][:max_fulltext]

        return ScreeningResult(
            query=query,
            total_papers=len(papers),
            screened_papers=screened_papers,
            papers_for_fulltext=papers_for_fulltext
        )


# 测试代码
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # 模拟搜索结果
    test_papers = [
        {
            "paper_id": "1706.03762",
            "title": "Attention Is All You Need",
            "authors": ["Vaswani", "Shazeer", "Parmar"],
            "year": 2017,
            "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms...",
            "url": "https://arxiv.org/abs/1706.03762",
            "source": "arxiv",
            "citation_count": 98000
        },
        {
            "paper_id": "1810.04805",
            "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
            "authors": ["Devlin", "Chang", "Lee"],
            "year": 2018,
            "abstract": "We introduce a new language representation model called BERT, which stands for Bidirectional Encoder Representations from Transformers...",
            "url": "https://arxiv.org/abs/1810.04805",
            "source": "arxiv",
            "citation_count": 75000
        },
        {
            "paper_id": "2001.08361",
            "title": "Scaling Laws for Neural Language Models",
            "authors": ["Kaplan", "McCandlish"],
            "year": 2020,
            "abstract": "We study empirical scaling laws for language model performance on the cross-entropy loss. The loss scales as a power-law with model size, dataset size, and the amount of compute used for training...",
            "url": "https://arxiv.org/abs/2001.08361",
            "source": "arxiv",
            "citation_count": 3000
        },
        {
            "paper_id": "some_unrelated",
            "title": "A Survey on Image Classification using CNN",
            "authors": ["Smith", "Johnson"],
            "year": 2021,
            "abstract": "This paper surveys various convolutional neural network architectures for image classification tasks...",
            "url": "https://example.com/paper",
            "source": "openalex",
            "citation_count": 100
        }
    ]

    screener = PaperScreener(
        qwen_api_key=os.getenv("QWEN_API_KEY"),
        max_fulltext=10
    )

    print("=" * 60)
    print("论文筛选器测试")
    print("=" * 60)

    result = screener.screen(
        query="Transformer 架构的发展和在 NLP 中的应用",
        papers=test_papers
    )

    print(f"\n查询: {result.query}")
    print(f"总论文数: {result.total_papers}")
    print(f"需要获取全文: {result.fulltext_count} 篇")

    print("\n筛选结果:")
    for p in result.screened_papers:
        ft_mark = "📄" if p.should_get_fulltext else "  "
        print(f"  {ft_mark} [{p.relevance_score}分] {p.title[:50]}...")
        print(f"       原因: {p.relevance_reason}")

    print("\n需要获取全文的论文:")
    for p in result.papers_for_fulltext:
        print(f"  - {p.title[:50]}... (arXiv: {p.arxiv_id})")
