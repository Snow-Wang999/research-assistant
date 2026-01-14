"""全文研究员 Agent

使用 PDF 全文（而非仅摘要）进行研究。
v0.4.0 新增。
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
from tools.paper_screener import PaperScreener, ScreeningResult, ScreenedPaper
from tools.pdf import PaperProcessor, ProcessedPaper
from utils.llm_client import QwenClient
from .decomposer import SubQuestion


@dataclass
class SupportingEvidence:
    """支持证据（句级引用）"""
    sentence: str           # 支持句原文
    page: int               # 页码
    position: str           # 位置标签 (@@page\tx0\tx1\ty0\ty1##)
    paper_title: str        # 来源论文标题
    paper_index: int        # 论文编号（用于引用标注）


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
    evidences: List[SupportingEvidence] = None  # 句级证据列表

    def __post_init__(self):
        if self.evidences is None:
            self.evidences = []

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

    COMPRESS_PROMPT = """你是一个严谨的学术研究助手。基于论文全文内容回答研究问题。

研究问题：{question}
研究目的：{purpose}

论文内容（每篇论文标注为 [P1], [P2] 等）：
{papers_content}

请基于以上论文内容，提供详细的研究发现，并引用具体的支持句。

输出 JSON 格式：
{{
  "findings": "综合研究发现（200-400字，在具体观点后标注来源如[P1][P2]）",
  "key_points": [
    "关键要点1 [P1]",
    "关键要点2 [P2]",
    "关键要点3 [P1][P3]",
    "关键要点4"
  ],
  "cited_papers": [
    {{
      "paper_id": "P1",
      "title": "论文标题",
      "key_contribution": "该论文对回答问题的核心贡献（30字内）"
    }}
  ],
  "supporting_sentences": [
    {{
      "paper_id": "P1",
      "sentence": "从论文中摘录的原句（支持某个关键发现的证据）",
      "supports": "该句支持的观点（简述）"
    }},
    {{
      "paper_id": "P2",
      "sentence": "另一个支持句...",
      "supports": "支持的观点"
    }}
  ]
}}

要求：
1. findings 必须基于论文全文的实际内容，标注来源 [P1][P2]
2. 每个 key_point 都应该标注论文来源
3. supporting_sentences 必须是论文中的原句，用于证据追溯
4. 每篇论文至少提供1-2个支持句"""

    def __init__(
        self,
        qwen_api_key: Optional[str] = None,
        searcher: Optional[UnifiedSearch] = None,
        max_fulltext_per_question: int = 5
    ):
        self.llm_client = QwenClient(api_key=qwen_api_key) if qwen_api_key else None
        self.searcher = searcher or UnifiedSearch()
        self.screener = PaperScreener(
            qwen_api_key=qwen_api_key,
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
        """格式化全文用于 prompt，添加论文编号标记 [P1], [P2] 等"""
        parts = []
        for i, pp in enumerate(processed_papers, 1):
            # 限制每篇论文的全文长度
            fulltext = pp.full_text[:8000] if len(pp.full_text) > 8000 else pp.full_text

            parts.append(
                f"=== [P{i}] {pp.title} ===\n"
                f"arXiv ID: {pp.arxiv_id}\n"
                f"摘要: {pp.abstract[:500]}...\n\n"
                f"全文内容:\n{fulltext}\n"
            )

        return "\n\n".join(parts)

    def _extract_sentences_with_positions(self, processed_paper: ProcessedPaper, paper_index: int) -> List[dict]:
        """从论文中提取句子及其位置信息"""
        sentences = []
        for chunk in processed_paper.chunks:
            # 获取该 chunk 的页码
            page = chunk.pages[0] if chunk.pages else 1
            position_tag = chunk.position_tags[0] if chunk.position_tags else ""

            # 简单句子分割
            chunk_sentences = re.split(r'(?<=[.!?。！？])\s+', chunk.text)
            for sent in chunk_sentences:
                sent = sent.strip()
                if len(sent) > 20:  # 过滤太短的句子
                    sentences.append({
                        "sentence": sent,
                        "page": page,
                        "position": position_tag,
                        "paper_index": paper_index,
                        "paper_title": processed_paper.title
                    })
        return sentences

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
        if not self.llm_client:
            return self._fallback_result(sub_question, processed_papers, screening_result)

        try:
            content = self._format_fulltext_for_prompt(processed_papers)

            prompt = self.COMPRESS_PROMPT.format(
                question=sub_question.question,
                purpose=sub_question.purpose,
                papers_content=content
            )

            # 使用通义千问 plus 模型（全文压缩是复杂任务）
            result_content = self.llm_client.chat(
                prompt=prompt,
                task_type="compress",
                max_tokens=2500,
                temperature=0.3,
                timeout=60.0
            )

            parsed = self._parse_response(result_content)

            if parsed:
                # 构建来源和句级证据
                sources, evidences = self._build_sources(
                    processed_papers,
                    parsed.get("cited_papers", []),
                    parsed.get("supporting_sentences", [])
                )

                return FulltextResearchResult(
                    sub_question=sub_question.question,
                    purpose=sub_question.purpose,
                    papers_searched=screening_result.total_papers,
                    papers_screened=len(screening_result.papers_for_fulltext),
                    papers_with_fulltext=len(processed_papers),
                    compressed_findings=parsed.get("findings", ""),
                    key_points=parsed.get("key_points", []),
                    sources=sources,
                    evidences=evidences
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
        if self.llm_client and relevant_papers:
            try:
                papers_text = self._format_abstracts_for_prompt(relevant_papers)
                prompt = self.COMPRESS_PROMPT.format(
                    question=sub_question.question,
                    purpose=sub_question.purpose,
                    papers_content=papers_text
                )

                # 使用通义千问 plus 模型（摘要压缩也是复杂任务）
                content = self.llm_client.chat(
                    prompt=prompt,
                    task_type="compress",
                    max_tokens=1500,
                    temperature=0.3,
                    timeout=30.0
                )

                parsed = self._parse_response(content)

                if parsed:
                    findings = parsed.get("findings", "")
                    key_points = parsed.get("key_points", [])
                    print(f"[FulltextAgent] LLM 压缩成功，findings 长度: {len(findings)}")
                else:
                    print("[FulltextAgent] JSON 解析失败，使用摘要提取")
                    findings, key_points = self._extract_from_abstracts(relevant_papers)

            except Exception as e:
                print(f"[FulltextAgent] LLM 压缩失败: {type(e).__name__}: {e}")
                # 回退：从摘要中提取关键内容
                findings, key_points = self._extract_from_abstracts(relevant_papers)
        else:
            print("[FulltextAgent] 无 API Key，使用摘要提取")
            findings, key_points = self._extract_from_abstracts(relevant_papers)

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
        cited_papers: List[dict],
        supporting_sentences: List[dict] = None
    ) -> tuple[List[dict], List[SupportingEvidence]]:
        """构建来源列表和句级证据"""
        sources = []
        evidences = []

        # 建立论文索引映射
        paper_index_map = {}  # paper_id (P1, P2) -> index
        for i, pp in enumerate(processed_papers, 1):
            paper_index_map[f"P{i}"] = i

        for i, pp in enumerate(processed_papers, 1):
            # 查找引用信息
            contribution = ""
            paper_id = f"P{i}"
            for cp in cited_papers:
                if cp.get("paper_id") == paper_id or cp.get("title", "").lower() in pp.title.lower():
                    contribution = cp.get("key_contribution", "")
                    break

            # 提取该论文的所有句子位置信息
            all_sentences = self._extract_sentences_with_positions(pp, i)

            sources.append({
                "title": pp.title,
                "arxiv_id": pp.arxiv_id,
                "abstract": pp.abstract,
                "has_fulltext": True,
                "fulltext_length": len(pp.full_text),
                "chunks_count": len(pp.chunks),
                "contribution": contribution,
                "paper_id": paper_id,
                "sentences_count": len(all_sentences)
            })

            # 从 LLM 返回的 supporting_sentences 中匹配该论文的证据
            if supporting_sentences:
                for ss in supporting_sentences:
                    if ss.get("paper_id") == paper_id:
                        # 尝试在论文句子中找到匹配的位置
                        sentence_text = ss.get("sentence", "")
                        page = 1
                        position = ""

                        # 模糊匹配找到最相近的句子
                        for sent_info in all_sentences:
                            if self._sentence_similarity(sentence_text, sent_info["sentence"]) > 0.5:
                                page = sent_info["page"]
                                position = sent_info["position"]
                                break

                        evidences.append(SupportingEvidence(
                            sentence=sentence_text,
                            page=page,
                            position=position,
                            paper_title=pp.title,
                            paper_index=i
                        ))

        return sources, evidences

    def _extract_from_abstracts(self, papers: List[ScreenedPaper]) -> tuple[str, List[str]]:
        """从论文摘要中提取关键发现（回退方案）

        Args:
            papers: 筛选后的论文列表

        Returns:
            (findings, key_points): 研究发现和关键要点
        """
        if not papers:
            return "未找到相关论文。", ["无可用信息"]

        # 构建研究发现：汇总摘要的关键句
        findings_parts = []
        key_points = []

        for i, p in enumerate(papers[:5], 1):  # 最多使用5篇
            abstract = p.abstract or ""
            if not abstract:
                continue

            # 提取摘要的第一句（通常是核心内容）
            first_sentence = abstract.split('.')[0].strip()
            if len(first_sentence) > 20:
                # 添加到发现中
                findings_parts.append(f"[{i}] {first_sentence}.")

                # 提取关键要点：使用论文的相关性描述或摘要前50字
                if p.relevance_reason:
                    key_points.append(f"{p.title[:40]}... - {p.relevance_reason}")
                else:
                    key_points.append(f"{p.title[:40]}... ({p.year})")

        if findings_parts:
            findings = f"基于 {len(papers)} 篇相关论文的摘要分析：\n\n" + "\n\n".join(findings_parts)
        else:
            findings = f"共检索到 {len(papers)} 篇相关论文，但摘要信息不完整。"

        if not key_points:
            key_points = [f"{p.title[:50]}..." for p in papers[:3]]

        return findings, key_points

    def _sentence_similarity(self, s1: str, s2: str) -> float:
        """简单的句子相似度计算（基于词重叠）"""
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union) if union else 0.0

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
            sources=[],
            evidences=[]
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
                "fulltext_length": len(pp.full_text),
                "paper_id": f"P{i}"
            }
            for i, pp in enumerate(processed_papers, 1)
        ]

        return FulltextResearchResult(
            sub_question=sub_question.question,
            purpose=sub_question.purpose,
            papers_searched=screening_result.total_papers,
            papers_screened=len(screening_result.papers_for_fulltext),
            papers_with_fulltext=len(processed_papers),
            compressed_findings=findings,
            key_points=key_points,
            sources=sources,
            evidences=[]
        )


class ParallelFulltextResearchRunner:
    """并行全文研究执行器"""

    def __init__(
        self,
        qwen_api_key: Optional[str] = None,
        max_workers: int = 2,  # 全文研究较重，减少并发
        max_fulltext_per_question: int = 5
    ):
        self.qwen_api_key = qwen_api_key
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
                    qwen_api_key=self.qwen_api_key,
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
                        sources=[],
                        evidences=[]
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
