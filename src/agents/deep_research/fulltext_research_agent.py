"""全文研究员 Agent

使用 PDF 全文（而非仅摘要）进行研究。
v0.4.0 新增。
"""

import httpx
import json
import re
from typing import List, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.search import UnifiedSearch
from tools.paper_screener import PaperScreener, ScreeningResult, ScreenedPaper
from tools.pdf import PaperProcessor, ProcessedPaper
from .decomposer import SubQuestion


@dataclass
class FulltextResearchResult:
    """全文研究结果"""
    sub_question: str
    purpose: str
    papers_searched: int      # 搜索到的论文数
    papers_screened: int      # 筛选后的论文数
    papers_with_fulltext: int # 获取到全文的论文数
    compressed_findings: str  # 压缩后的研究发现
    key_points: List[str]     # 关键要点
    sources: List[dict]       # 引用来源（含全文位置）

    @property
    def papers_found(self) -> int:
        """兼容 ResearchResult 接口，返回搜索到的论文数"""
        return self.papers_searched


class FulltextResearchAgent:
    """
    全文研究员 Agent

    流程：
    1. 搜索论文（摘要）
    2. 筛选相关论文
    3. 下载 PDF 全文
    4. 使用全文进行 LLM 压缩
    """

    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

    COMPRESS_PROMPT = """你是一个严谨的学术研究助手。基于论文全文内容回答研究问题。

研究问题：{question}
研究目的：{purpose}

论文内容：
{papers_content}

请基于以上论文内容，提供详细的研究发现。

输出 JSON 格式：
{{
  "findings": "综合研究发现（200-400字，必须有具体内容支撑，引用具体论文）",
  "key_points": [
    "关键要点1（来自论文的具体发现，标注来源）",
    "关键要点2",
    "关键要点3",
    "关键要点4"
  ],
  "cited_papers": [
    {{
      "title": "论文标题",
      "key_contribution": "该论文对回答问题的核心贡献（30字内）"
    }}
  ]
}}

要求：
1. findings 必须基于论文全文的实际内容
2. 每个 key_point 都应该有论文支撑
3. 引用具体数据、方法、结论时要准确"""

    def __init__(
        self,
        deepseek_api_key: Optional[str] = None,
        searcher: Optional[UnifiedSearch] = None,
        max_fulltext_per_question: int = 5
    ):
        self.api_key = deepseek_api_key
        self.searcher = searcher or UnifiedSearch()
        self.screener = PaperScreener(
            deepseek_api_key=deepseek_api_key,
            max_fulltext=max_fulltext_per_question
        )
        self.paper_processor = PaperProcessor()
        self.max_fulltext = max_fulltext_per_question

    def research(self, sub_question: SubQuestion, limit: int = 10) -> FulltextResearchResult:
        """
        对单个子问题进行全文研究

        Args:
            sub_question: 子问题
            limit: 初始搜索的论文数量

        Returns:
            FulltextResearchResult: 研究结果
        """
        # 1. 搜索论文
        print(f"[FulltextAgent] 搜索: {sub_question.question[:30]}...")
        papers = self._search_papers(sub_question, limit)

        if not papers:
            return self._empty_result(sub_question)

        # 2. 筛选论文
        print(f"[FulltextAgent] 筛选 {len(papers)} 篇论文...")
        screening_result = self.screener.screen(
            query=sub_question.question,
            papers=papers,
            max_fulltext=self.max_fulltext
        )

        if not screening_result.papers_for_fulltext:
            # 没有需要获取全文的论文，使用摘要
            return self._research_with_abstracts(sub_question, papers, screening_result)

        # 3. 获取全文
        print(f"[FulltextAgent] 获取 {len(screening_result.papers_for_fulltext)} 篇论文全文...")
        processed_papers = self._get_fulltexts(screening_result.papers_for_fulltext)

        if not processed_papers:
            # 全文获取失败，回退到摘要
            return self._research_with_abstracts(sub_question, papers, screening_result)

        # 4. 使用全文进行研究
        print(f"[FulltextAgent] 使用 {len(processed_papers)} 篇全文进行研究...")
        return self._research_with_fulltext(sub_question, processed_papers, screening_result)

    def _search_papers(self, sub_question: SubQuestion, limit: int) -> List[dict]:
        """搜索论文"""
        all_papers = []

        for keyword in sub_question.search_keywords[:3]:
            try:
                result = self.searcher.search(keyword, limit=limit)
                for paper in result.papers:
                    paper_dict = {
                        "paper_id": paper.paper_id,
                        "title": paper.title,
                        "authors": paper.authors[:3],
                        "year": paper.year,
                        "abstract": paper.abstract,
                        "url": paper.url,
                        "source": paper.source,
                        "citation_count": paper.citation_count
                    }
                    all_papers.append(paper_dict)
            except Exception as e:
                print(f"[FulltextAgent] 搜索出错: {e}")

        # 去重
        seen = set()
        unique = []
        for p in all_papers:
            key = p["title"].lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(p)

        return unique

    def _get_fulltexts(self, screened_papers: List[ScreenedPaper]) -> List[ProcessedPaper]:
        """获取论文全文"""
        processed = []

        for sp in screened_papers:
            arxiv_id = sp.arxiv_id
            if not arxiv_id:
                print(f"[FulltextAgent] 跳过非 arXiv 论文: {sp.title[:30]}...")
                continue

            try:
                result = self.paper_processor.process(arxiv_id)
                if result.success:
                    # 将筛选信息附加到处理结果
                    result.relevance_score = sp.relevance_score
                    result.relevance_reason = sp.relevance_reason
                    processed.append(result)
                    print(f"[FulltextAgent] 获取全文成功: {arxiv_id}")
                else:
                    print(f"[FulltextAgent] 获取全文失败: {arxiv_id} - {result.error}")
            except Exception as e:
                print(f"[FulltextAgent] 处理出错: {arxiv_id} - {e}")

        return processed

    def _format_fulltext_for_prompt(self, processed_papers: List[ProcessedPaper]) -> str:
        """格式化全文用于 prompt"""
        parts = []
        for i, pp in enumerate(processed_papers, 1):
            # 限制每篇论文的全文长度
            fulltext = pp.full_text[:8000] if len(pp.full_text) > 8000 else pp.full_text

            parts.append(
                f"=== 论文 {i}: {pp.title} ===\n"
                f"arXiv ID: {pp.arxiv_id}\n"
                f"摘要: {pp.abstract[:500]}...\n\n"
                f"全文内容:\n{fulltext}\n"
            )

        return "\n\n".join(parts)

    def _format_abstracts_for_prompt(self, screened_papers: List[ScreenedPaper]) -> str:
        """格式化摘要用于 prompt"""
        parts = []
        for i, sp in enumerate(screened_papers, 1):
            parts.append(
                f"=== 论文 {i}: {sp.title} ===\n"
                f"年份: {sp.year}\n"
                f"相关性评分: {sp.relevance_score}/5\n"
                f"相关性原因: {sp.relevance_reason}\n\n"
                f"摘要:\n{sp.abstract}\n"
            )
        return "\n\n".join(parts)

    def _research_with_fulltext(
        self,
        sub_question: SubQuestion,
        processed_papers: List[ProcessedPaper],
        screening_result: ScreeningResult
    ) -> FulltextResearchResult:
        """使用全文进行研究"""
        if not self.api_key:
            return self._fallback_result(sub_question, processed_papers, screening_result)

        try:
            content = self._format_fulltext_for_prompt(processed_papers)

            prompt = self.COMPRESS_PROMPT.format(
                question=sub_question.question,
                purpose=sub_question.purpose,
                papers_content=content
            )

            response = httpx.post(
                self.DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.3
                },
                timeout=45.0
            )
            response.raise_for_status()

            result_content = response.json()["choices"][0]["message"]["content"]
            parsed = self._parse_response(result_content)

            if parsed:
                sources = self._build_sources(processed_papers, parsed.get("cited_papers", []))

                return FulltextResearchResult(
                    sub_question=sub_question.question,
                    purpose=sub_question.purpose,
                    papers_searched=screening_result.total_papers,
                    papers_screened=len(screening_result.papers_for_fulltext),
                    papers_with_fulltext=len(processed_papers),
                    compressed_findings=parsed.get("findings", ""),
                    key_points=parsed.get("key_points", []),
                    sources=sources
                )

        except Exception as e:
            print(f"[FulltextAgent] LLM 研究出错: {e}")

        return self._fallback_result(sub_question, processed_papers, screening_result)

    def _research_with_abstracts(
        self,
        sub_question: SubQuestion,
        papers: List[dict],
        screening_result: ScreeningResult
    ) -> FulltextResearchResult:
        """使用摘要进行研究（回退方案）- 也调用 LLM"""
        print("[FulltextAgent] 回退到摘要研究...")

        # 使用筛选后的论文摘要
        relevant_papers = [
            p for p in screening_result.screened_papers
            if p.relevance_score >= 3
        ][:10]  # 增加到 10 篇

        if not relevant_papers:
            relevant_papers = screening_result.screened_papers[:5]

        # 调用 LLM 压缩（使用摘要而非全文）
        if self.api_key and relevant_papers:
            try:
                papers_text = self._format_abstracts_for_prompt(relevant_papers)
                prompt = self.COMPRESS_PROMPT.format(
                    question=sub_question.question,
                    purpose=sub_question.purpose,
                    papers_content=papers_text
                )

                response = httpx.post(
                    self.DEEPSEEK_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 1500,
                        "temperature": 0.3
                    },
                    timeout=30.0
                )
                response.raise_for_status()

                content = response.json()["choices"][0]["message"]["content"]
                parsed = self._parse_response(content)

                if parsed:
                    findings = parsed.get("findings", "")
                    key_points = parsed.get("key_points", [])
                    print(f"[FulltextAgent] LLM 压缩成功，findings 长度: {len(findings)}")
                else:
                    findings = f"基于 {len(relevant_papers)} 篇相关论文的摘要分析。"
                    key_points = [f"{p.title[:50]}..." for p in relevant_papers[:3]]

            except Exception as e:
                print(f"[FulltextAgent] LLM 压缩失败: {e}")
                findings = f"基于 {len(relevant_papers)} 篇相关论文的摘要分析。"
                key_points = [f"{p.title[:50]}..." for p in relevant_papers[:3]]
        else:
            findings = f"基于 {len(relevant_papers)} 篇相关论文的摘要分析。"
            key_points = [f"{p.title[:50]}..." for p in relevant_papers[:3]]

        sources = [
            {
                "title": p.title,
                "authors": p.authors,
                "year": p.year,
                "abstract": p.abstract,
                "url": p.url,
                "source": p.source,
                "has_fulltext": False
            }
            for p in relevant_papers
        ]

        return FulltextResearchResult(
            sub_question=sub_question.question,
            purpose=sub_question.purpose,
            papers_searched=len(papers),
            papers_screened=len(screening_result.papers_for_fulltext),
            papers_with_fulltext=0,
            compressed_findings=findings,
            key_points=key_points,
            sources=sources
        )

    def _build_sources(
        self,
        processed_papers: List[ProcessedPaper],
        cited_papers: List[dict]
    ) -> List[dict]:
        """构建来源列表"""
        sources = []
        for pp in processed_papers:
            # 查找引用信息
            contribution = ""
            for cp in cited_papers:
                if cp.get("title", "").lower() in pp.title.lower():
                    contribution = cp.get("key_contribution", "")
                    break

            sources.append({
                "title": pp.title,
                "arxiv_id": pp.arxiv_id,
                "abstract": pp.abstract,
                "has_fulltext": True,
                "fulltext_length": len(pp.full_text),
                "chunks_count": len(pp.chunks),
                "contribution": contribution
            })

        return sources

    def _parse_response(self, content: str) -> Optional[dict]:
        """解析 LLM 响应"""
        try:
            return json.loads(content)
        except:
            pass

        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass

        return None

    def _empty_result(self, sub_question: SubQuestion) -> FulltextResearchResult:
        """返回空结果"""
        return FulltextResearchResult(
            sub_question=sub_question.question,
            purpose=sub_question.purpose,
            papers_searched=0,
            papers_screened=0,
            papers_with_fulltext=0,
            compressed_findings="未找到相关论文",
            key_points=["无法获取相关信息"],
            sources=[]
        )

    def _fallback_result(
        self,
        sub_question: SubQuestion,
        processed_papers: List[ProcessedPaper],
        screening_result: ScreeningResult
    ) -> FulltextResearchResult:
        """回退结果"""
        findings = f"成功获取 {len(processed_papers)} 篇论文全文。"
        key_points = [f"{pp.title[:50]}..." for pp in processed_papers[:3]]

        sources = [
            {
                "title": pp.title,
                "arxiv_id": pp.arxiv_id,
                "has_fulltext": True,
                "fulltext_length": len(pp.full_text)
            }
            for pp in processed_papers
        ]

        return FulltextResearchResult(
            sub_question=sub_question.question,
            purpose=sub_question.purpose,
            papers_searched=screening_result.total_papers,
            papers_screened=len(screening_result.papers_for_fulltext),
            papers_with_fulltext=len(processed_papers),
            compressed_findings=findings,
            key_points=key_points,
            sources=sources
        )


class ParallelFulltextResearchRunner:
    """并行全文研究执行器"""

    def __init__(
        self,
        deepseek_api_key: Optional[str] = None,
        max_workers: int = 2,  # 全文研究较重，减少并发
        max_fulltext_per_question: int = 5
    ):
        self.deepseek_api_key = deepseek_api_key
        self.max_workers = max_workers
        self.max_fulltext = max_fulltext_per_question

    def run(
        self,
        sub_questions: List[SubQuestion],
        limit_per_question: int = 10
    ) -> List[FulltextResearchResult]:
        """并行执行全文研究"""
        results = []
        searcher = UnifiedSearch()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_question = {}

            for sq in sub_questions:
                agent = FulltextResearchAgent(
                    deepseek_api_key=self.deepseek_api_key,
                    searcher=searcher,
                    max_fulltext_per_question=self.max_fulltext
                )
                future = executor.submit(agent.research, sq, limit_per_question)
                future_to_question[future] = sq

            for future in as_completed(future_to_question):
                sq = future_to_question[future]
                try:
                    result = future.result()
                    results.append(result)
                    print(f"[FulltextRunner] 完成: {sq.question[:30]}...")
                except Exception as e:
                    print(f"[FulltextRunner] 出错: {sq.question[:30]}... - {e}")
                    results.append(FulltextResearchResult(
                        sub_question=sq.question,
                        purpose=sq.purpose,
                        papers_searched=0,
                        papers_screened=0,
                        papers_with_fulltext=0,
                        compressed_findings="研究过程出错",
                        key_points=[],
                        sources=[]
                    ))

        return results


# 测试代码
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    agent = FulltextResearchAgent(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        max_fulltext_per_question=3
    )

    test_question = SubQuestion(
        question="Transformer 架构的核心原理",
        purpose="了解 Transformer 基础",
        search_keywords=["Transformer architecture", "attention mechanism"]
    )

    print("=" * 60)
    print("全文研究员 Agent 测试")
    print("=" * 60)

    result = agent.research(test_question, limit=5)

    print(f"\n子问题: {result.sub_question}")
    print(f"搜索论文数: {result.papers_searched}")
    print(f"筛选论文数: {result.papers_screened}")
    print(f"获取全文数: {result.papers_with_fulltext}")
    print(f"\n研究发现:\n{result.compressed_findings}")
    print(f"\n关键要点:")
    for i, point in enumerate(result.key_points, 1):
        print(f"  {i}. {point}")
