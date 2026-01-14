"""研究员 Agent

负责对单个子问题进行搜索研究，并压缩总结结果。
参考 Open Deep Research 的 Researcher Subgraph 设计。
"""
import json
import re
from typing import List, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.search import UnifiedSearch
from utils.llm_client import QwenClient
from .decomposer import SubQuestion


@dataclass
class ResearchResult:
    """单个子问题的研究结果"""
    sub_question: str           # 子问题
    purpose: str                # 研究目的
    papers_found: int           # 找到的论文数
    compressed_findings: str    # 压缩后的研究发现
    key_points: List[str]       # 关键要点
    sources: List[dict]         # 引用来源


class ResearchAgent:
    """
    研究员 Agent

    负责对单个子问题进行独立研究：
    1. 使用多个关键词搜索
    2. 整合 arXiv 和 OpenAlex 的结果
    3. 使用 LLM 压缩和总结发现
    """

    COMPRESS_PROMPT = """你是一个严谨的学术研究助手。你的任务是：
1. 严格筛选与研究问题**直接相关**的论文
2. 基于相关论文总结研究发现

研究问题：{question}
研究目的：{purpose}

搜索到的论文：
{papers_text}

**重要**：请严格评估每篇论文与研究问题的相关性。
- 只有**直接讨论**研究问题核心内容的论文才算相关
- 仅仅提到相关词汇但主题不同的论文，应排除
- 例如：研究问题是"Transformer vs RNN对比"，则只有直接对比两者的论文才相关

输出 JSON 格式：
{{
  "findings": "基于相关论文的综合发现（100-200字，必须有具体内容支撑）",
  "key_points": [
    "关键要点1（基于论文的具体发现）",
    "关键要点2",
    "关键要点3"
  ],
  "relevant_papers": [
    {{
      "title": "论文完整标题（必须与输入完全一致）",
      "year": 年份,
      "relevance_score": 5,
      "relevance": "具体说明该论文如何回答研究问题（20字内）"
    }}
  ]
}}

相关性评分标准（relevance_score）：
- 5分：直接对比/研究该问题的核心论文（必选）
- 4分：深入讨论问题某一方面的重要论文（应选）
- 3分：提供相关背景或部分证据的论文（可选，但优先级低）
- 1-2分：仅间接相关或主题不符，**绝对不要包含**

要求：
1. relevant_papers 只包含 relevance_score >= 4 的论文（严格筛选）
2. **平衡新旧论文**：ARXIV论文代表最新研究进展，OPENALEX论文代表经典文献，两者都要考虑
3. **不要只看引用数**：新论文（ARXIV）引用数低但可能更切题，不要因为引用数低就排除
4. findings 必须基于所选论文的实际内容，不要编造
5. 如果没有高度相关的论文，诚实说明"""

    def __init__(
        self,
        qwen_api_key: Optional[str] = None,
        searcher: Optional[UnifiedSearch] = None
    ):
        self.llm_client = QwenClient(api_key=qwen_api_key) if qwen_api_key else None
        self.searcher = searcher or UnifiedSearch()

    def research(self, sub_question: SubQuestion, limit: int = 5) -> ResearchResult:
        """
        对单个子问题进行研究

        Args:
            sub_question: 子问题
            limit: 每个来源的论文数量限制

        Returns:
            ResearchResult: 研究结果
        """
        # 1. 搜索论文
        papers = self._search_papers(sub_question, limit)

        if not papers:
            return ResearchResult(
                sub_question=sub_question.question,
                purpose=sub_question.purpose,
                papers_found=0,
                compressed_findings="未找到相关论文",
                key_points=["无法获取相关信息"],
                sources=[]
            )

        # 2. 压缩总结
        if self.llm_client:
            result = self._compress_with_llm(sub_question, papers)
        else:
            result = self._compress_fallback(sub_question, papers)

        return result

    def _search_papers(self, sub_question: SubQuestion, limit: int) -> List[dict]:
        """搜索论文"""
        all_papers = []

        # 使用多个关键词搜索
        for keyword in sub_question.search_keywords[:3]:  # 最多3个关键词
            try:
                result = self.searcher.search(keyword, limit=limit)
                for paper in result.papers:
                    paper_dict = {
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
                print(f"[ResearchAgent] 搜索 '{keyword}' 出错: {e}")

        # 去重（基于标题）
        seen_titles = set()
        unique_papers = []
        for p in all_papers:
            title_lower = p["title"].lower().strip()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                unique_papers.append(p)

        return unique_papers[:limit * 2]  # 返回更多以供筛选

    def _format_papers_for_prompt(self, papers: List[dict]) -> str:
        """格式化论文列表"""
        lines = []
        for i, p in enumerate(papers, 1):
            source = p.get('source', 'unknown').upper()
            year = p.get('year', 'N/A')
            citations = p.get('citation_count', 0) or 0
            abstract = p.get('abstract', '')[:300] if p.get('abstract') else ''

            lines.append(
                f"[{i}] [{source}] {p['title']}\n"
                f"    年份: {year}, 引用: {citations}\n"
                f"    摘要: {abstract}..."
            )
        return "\n\n".join(lines)

    def _compress_with_llm(self, sub_question: SubQuestion, papers: List[dict]) -> ResearchResult:
        """使用 LLM 压缩总结"""
        try:
            papers_text = self._format_papers_for_prompt(papers)

            prompt = self.COMPRESS_PROMPT.format(
                question=sub_question.question,
                purpose=sub_question.purpose,
                papers_text=papers_text
            )

            print(f"[ResearchAgent] 调用 LLM 压缩: {sub_question.question[:30]}...")

            # 使用通义千问 plus 模型（论文压缩是复杂任务）
            content = self.llm_client.chat(
                prompt=prompt,
                task_type="compress",
                max_tokens=1500,
                temperature=0.3,
                timeout=25.0
            )

            print(f"[ResearchAgent] LLM 响应长度: {len(content)} 字符")
            parsed = self._parse_response(content)

            if parsed:
                print(f"[ResearchAgent] JSON 解析成功，findings 长度: {len(parsed.get('findings', ''))}")
                # 提取相关论文作为来源（保留完整信息）
                sources = []
                for rp in parsed.get("relevant_papers", []):
                    # 在原始论文列表中查找匹配
                    for p in papers:
                        if rp.get("title", "").lower() in p["title"].lower():
                            sources.append({
                                "title": p["title"],
                                "authors": p.get("authors", []),
                                "year": p.get("year"),
                                "abstract": p.get("abstract", ""),
                                "url": p.get("url"),
                                "source": p.get("source"),
                                "citation_count": p.get("citation_count"),
                                "relevance": rp.get("relevance", "")
                            })
                            break

                # 检查来源平衡：如果 LLM 筛选后没有 arXiv 论文，补充一些
                arxiv_in_sources = [s for s in sources if s.get("source") == "arxiv"]
                if not arxiv_in_sources:
                    # 从原始列表中找 arXiv 论文补充
                    arxiv_papers = [p for p in papers if p.get("source") == "arxiv"]
                    arxiv_papers.sort(key=lambda x: x.get("year", 0) or 0, reverse=True)
                    for p in arxiv_papers[:2]:  # 补充最多2篇最新的 arXiv 论文
                        sources.append({
                            "title": p["title"],
                            "authors": p.get("authors", []),
                            "year": p.get("year"),
                            "abstract": p.get("abstract", ""),
                            "url": p.get("url"),
                            "source": p.get("source"),
                            "citation_count": p.get("citation_count"),
                            "relevance": "最新研究（补充）"
                        })
                    print(f"[ResearchAgent] 补充了 {min(2, len(arxiv_papers))} 篇 arXiv 论文")

                print(f"[ResearchAgent] 筛选出 {len(sources)} 篇相关论文")
                return ResearchResult(
                    sub_question=sub_question.question,
                    purpose=sub_question.purpose,
                    papers_found=len(papers),
                    compressed_findings=parsed.get("findings", ""),
                    key_points=parsed.get("key_points", []),
                    sources=sources if sources else self._extract_top_sources(papers)
                )
            else:
                print(f"[ResearchAgent] JSON 解析失败，原始内容前200字: {content[:200]}")

        except Exception as e:
            print(f"[ResearchAgent] LLM 压缩出错: {type(e).__name__}: {e}")

        return self._compress_fallback(sub_question, papers)

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

    def _extract_top_sources(self, papers: List[dict], limit: int = 5) -> List[dict]:
        """提取最重要的来源（平衡 arXiv 和 OpenAlex）"""
        # 分离 arXiv 和 OpenAlex 论文
        arxiv_papers = [p for p in papers if p.get("source") == "arxiv"]
        openalex_papers = [p for p in papers if p.get("source") != "arxiv"]

        # arXiv 按年份排序（最新优先）
        arxiv_papers.sort(key=lambda x: x.get("year", 0) or 0, reverse=True)
        # OpenAlex 按引用数排序
        openalex_papers.sort(key=lambda x: x.get("citation_count", 0) or 0, reverse=True)

        # 平衡选择：各取一半
        half_limit = max(1, limit // 2)
        selected_arxiv = arxiv_papers[:half_limit]
        selected_openalex = openalex_papers[:limit - len(selected_arxiv)]

        # 如果某一来源不足，用另一来源补充
        if len(selected_arxiv) < half_limit:
            selected_openalex = openalex_papers[:limit - len(selected_arxiv)]
        if len(selected_openalex) < limit - half_limit:
            selected_arxiv = arxiv_papers[:limit - len(selected_openalex)]

        sources = []
        for p in selected_arxiv:
            sources.append({
                "title": p["title"],
                "authors": p.get("authors", []),
                "year": p.get("year"),
                "abstract": p.get("abstract", ""),
                "url": p.get("url"),
                "source": p.get("source"),
                "citation_count": p.get("citation_count"),
                "relevance": "最新研究"
            })
        for p in selected_openalex:
            sources.append({
                "title": p["title"],
                "authors": p.get("authors", []),
                "year": p.get("year"),
                "abstract": p.get("abstract", ""),
                "url": p.get("url"),
                "source": p.get("source"),
                "citation_count": p.get("citation_count"),
                "relevance": "经典文献"
            })

        return sources

    def _compress_fallback(self, sub_question: SubQuestion, papers: List[dict]) -> ResearchResult:
        """回退方案：从摘要中提取关键信息"""
        print("[ResearchAgent] 使用回退方案（摘要提取）")

        # 按引用数排序
        sorted_papers = sorted(
            papers,
            key=lambda x: x.get("citation_count", 0) or 0,
            reverse=True
        )

        # 从摘要中提取关键发现
        findings_parts = []
        key_points = []

        for i, p in enumerate(sorted_papers[:5], 1):
            abstract = p.get("abstract", "")
            if not abstract:
                continue

            # 提取摘要的第一句
            first_sentence = abstract.split('.')[0].strip()
            if len(first_sentence) > 20:
                findings_parts.append(f"[{i}] {p['title'][:50]}... : {first_sentence}.")
                # 关键要点：年份 + 摘要前80字
                key_points.append(f"({p.get('year', 'N/A')}) {abstract[:80]}...")

        # 构建研究发现
        if findings_parts:
            findings = f"基于 {len(papers)} 篇论文的摘要分析：\n\n" + "\n\n".join(findings_parts)
        else:
            findings = f"共找到 {len(papers)} 篇相关论文。"
            if sorted_papers:
                top = sorted_papers[0]
                findings += f" 最相关的论文是《{top['title'][:50]}...》（{top.get('year', 'N/A')}年）"

        # 如果没有提取到关键要点，使用标题
        if not key_points:
            key_points = [f"{p['title'][:60]}..." for p in sorted_papers[:3]]

        return ResearchResult(
            sub_question=sub_question.question,
            purpose=sub_question.purpose,
            papers_found=len(papers),
            compressed_findings=findings,
            key_points=key_points,
            sources=self._extract_top_sources(papers)
        )


class ParallelResearchRunner:
    """
    并行研究执行器

    并行执行多个子问题的研究，提高效率。
    """

    def __init__(
        self,
        qwen_api_key: Optional[str] = None,
        max_workers: int = 3
    ):
        self.qwen_api_key = qwen_api_key
        self.max_workers = max_workers

    def run(
        self,
        sub_questions: List[SubQuestion],
        limit_per_question: int = 5
    ) -> List[ResearchResult]:
        """
        并行执行多个子问题的研究

        Args:
            sub_questions: 子问题列表
            limit_per_question: 每个问题的论文数量限制

        Returns:
            List[ResearchResult]: 研究结果列表
        """
        results = []

        # 创建统一搜索器（共享）
        searcher = UnifiedSearch()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_question = {}
            for sq in sub_questions:
                agent = ResearchAgent(
                    qwen_api_key=self.qwen_api_key,
                    searcher=searcher
                )
                future = executor.submit(agent.research, sq, limit_per_question)
                future_to_question[future] = sq

            # 收集结果
            for future in as_completed(future_to_question):
                sq = future_to_question[future]
                try:
                    result = future.result()
                    results.append(result)
                    print(f"[ResearchRunner] 完成: {sq.question[:30]}...")
                except Exception as e:
                    print(f"[ResearchRunner] 研究出错: {sq.question[:30]}... - {e}")
                    # 返回空结果
                    results.append(ResearchResult(
                        sub_question=sq.question,
                        purpose=sq.purpose,
                        papers_found=0,
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

    # 测试单个研究员
    agent = ResearchAgent(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY")
    )

    test_question = SubQuestion(
        question="Transformer 架构的核心原理和在 NLP 中的应用",
        purpose="了解 Transformer 基础",
        search_keywords=["Transformer NLP", "attention mechanism"]
    )

    print("=" * 60)
    print("研究员 Agent 测试")
    print("=" * 60)

    result = agent.research(test_question, limit=5)

    print(f"\n子问题: {result.sub_question}")
    print(f"研究目的: {result.purpose}")
    print(f"找到论文数: {result.papers_found}")
    print(f"\n研究发现:\n{result.compressed_findings}")
    print(f"\n关键要点:")
    for i, point in enumerate(result.key_points, 1):
        print(f"  {i}. {point}")
    print(f"\n引用来源 ({len(result.sources)}):")
    for src in result.sources[:3]:
        print(f"  - {src['title'][:50]}... ({src.get('year', 'N/A')})")
