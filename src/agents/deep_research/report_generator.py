"""研究报告生成器

将多个子问题的研究结果整合为一份完整的研究报告。
参考 Open Deep Research 的 final_report_generation 设计。
"""
import httpx
import json
import re
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime

from .decomposer import DecompositionResult
from .research_agent import ResearchResult


@dataclass
class ResearchReport:
    """研究报告"""
    title: str                  # 报告标题
    overview: str               # 概述
    sections: List[dict]        # 各部分内容
    conclusion: str             # 综合结论
    sources: List[dict]         # 所有引用来源
    metadata: dict              # 元数据


class ReportGenerator:
    """
    研究报告生成器

    将多个子问题的研究结果整合为一份结构化的研究报告。
    支持 Markdown 格式输出。
    """

    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

    REPORT_PROMPT = """你是一个学术研究报告撰写专家。根据研究问题和各子问题的研究结果，生成一份结构化的研究报告。

原始研究问题：{original_query}
问题类型：{query_type}
研究策略：{research_strategy}

各子问题研究结果：
{research_findings}

**可引用的论文列表**（请在正文中使用 [编号] 格式引用）：
{paper_list}

任务：生成一份完整的研究报告，**必须在正文中标注引用来源**。

输出 JSON 格式：
{{
  "title": "报告标题（简洁有力，10-20字）",
  "overview": "研究概述，包含引用标注如[1][2]（100-150字）",
  "sections": [
    {{
      "heading": "章节标题",
      "content": "章节内容，**必须包含引用标注**如[1][3]（详细分析，100-200字）",
      "key_findings": ["发现1 [引用编号]", "发现2 [引用编号]"]
    }}
  ],
  "conclusion": "综合结论（100-150字，回答原始问题，给出建议或展望）",
  "key_takeaways": [
    "核心要点1（20字内）",
    "核心要点2（20字内）",
    "核心要点3（20字内）"
  ]
}}

**引用要求**（非常重要）：
1. 每个具体观点/发现后面必须标注来源，如"Transformer的自注意力机制能够捕获长程依赖[1][3]"
2. 使用方括号+数字格式，如 [1]、[2]、[1][3]
3. 只引用与该观点直接相关的论文，不要滥用引用
4. 如果某个观点来自多篇论文，可以标注多个，如 [1][2][5]

报告要求：
1. 标题应该直接反映研究主题
2. 概述需要说明研究了什么、怎么研究的、发现了什么
3. 每个 section 对应一个子问题，但标题应该是内容导向的
4. 结论需要综合所有发现，直接回答用户的原始问题
5. **所有具体发现必须有引用支撑**

特殊处理：
- 对比类问题：sections 应该包括各对象分析 + 对比总结
- 综述类问题：sections 应该按主题或时间线组织
- 趋势类问题：sections 应该包括历史回顾、现状分析、未来展望"""

    def __init__(self, deepseek_api_key: Optional[str] = None):
        self.api_key = deepseek_api_key

    def generate(
        self,
        decomposition: DecompositionResult,
        research_results: List[ResearchResult]
    ) -> ResearchReport:
        """
        生成研究报告

        Args:
            decomposition: 问题分解结果
            research_results: 各子问题的研究结果

        Returns:
            ResearchReport: 研究报告
        """
        if not research_results:
            return self._empty_report(decomposition.original_query)

        if self.api_key:
            report = self._generate_with_llm(decomposition, research_results)
        else:
            report = self._generate_fallback(decomposition, research_results)

        return report

    def _format_research_findings(self, results: List[ResearchResult]) -> str:
        """格式化研究结果用于 prompt"""
        lines = []
        for i, result in enumerate(results, 1):
            lines.append(f"## 子问题 {i}: {result.sub_question}")
            lines.append(f"研究目的: {result.purpose}")
            lines.append(f"找到论文: {result.papers_found} 篇")
            lines.append(f"\n研究发现:\n{result.compressed_findings}")

            if result.key_points:
                lines.append("\n关键要点:")
                for point in result.key_points:
                    lines.append(f"- {point}")

            lines.append("\n" + "-" * 40 + "\n")

        return "\n".join(lines)

    def _collect_all_papers(self, results: List[ResearchResult]) -> List[dict]:
        """收集所有论文并去重"""
        seen_titles = set()
        all_papers = []

        for result in results:
            for src in result.sources:
                title = src.get("title", "").lower().strip()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    all_papers.append(src)

        # 按引用数排序，高引用论文优先
        all_papers.sort(
            key=lambda x: x.get("citation_count", 0) or 0,
            reverse=True
        )

        return all_papers

    def _format_paper_list(self, papers: List[dict]) -> str:
        """格式化论文列表，带编号"""
        if not papers:
            return "（无可引用的论文）"

        lines = []
        for i, p in enumerate(papers, 1):
            title = p.get("title", "未知标题")
            year = p.get("year", "N/A")
            source = p.get("source", "unknown").upper()
            relevance = p.get("relevance", "")

            line = f"[{i}] {title} ({source}, {year})"
            if relevance:
                line += f" - {relevance}"
            lines.append(line)

        return "\n".join(lines)

    def _generate_with_llm(
        self,
        decomposition: DecompositionResult,
        research_results: List[ResearchResult]
    ) -> ResearchReport:
        """使用 LLM 生成报告"""
        try:
            findings_text = self._format_research_findings(research_results)

            # 收集所有论文并编号
            all_papers = self._collect_all_papers(research_results)
            paper_list_text = self._format_paper_list(all_papers)

            prompt = self.REPORT_PROMPT.format(
                original_query=decomposition.original_query,
                query_type=decomposition.query_type,
                research_strategy=decomposition.research_strategy,
                research_findings=findings_text,
                paper_list=paper_list_text
            )

            response = httpx.post(
                self.DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.3
                },
                timeout=20.0  # 缩短API超时
            )
            response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"]
            parsed = self._parse_response(content)

            if parsed:
                return self._format_report(decomposition, research_results, parsed)

        except Exception as e:
            print(f"[ReportGenerator] LLM 生成出错: {e}")

        return self._generate_fallback(decomposition, research_results)

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

    def _format_report(
        self,
        decomposition: DecompositionResult,
        research_results: List[ResearchResult],
        parsed: dict
    ) -> ResearchReport:
        """格式化报告"""
        # 使用统一的论文收集方法，保持编号一致性
        all_sources = self._collect_all_papers(research_results)

        return ResearchReport(
            title=parsed.get("title", decomposition.original_query),
            overview=parsed.get("overview", ""),
            sections=parsed.get("sections", []),
            conclusion=parsed.get("conclusion", ""),
            sources=all_sources,
            metadata={
                "original_query": decomposition.original_query,
                "query_type": decomposition.query_type,
                "research_strategy": decomposition.research_strategy,
                "sub_questions_count": len(decomposition.sub_questions),
                "total_papers": sum(r.papers_found for r in research_results),
                "generated_at": datetime.now().isoformat(),
                "key_takeaways": parsed.get("key_takeaways", [])
            }
        )

    def _generate_fallback(
        self,
        decomposition: DecompositionResult,
        research_results: List[ResearchResult]
    ) -> ResearchReport:
        """回退方案：简单整合"""
        sections = []
        for result in research_results:
            sections.append({
                "heading": result.sub_question[:50],
                "content": result.compressed_findings,
                "key_findings": result.key_points
            })

        # 收集所有来源
        all_sources = []
        for result in research_results:
            all_sources.extend(result.sources)

        # 简单概述
        total_papers = sum(r.papers_found for r in research_results)
        overview = f"本研究围绕「{decomposition.original_query}」展开，分解为 {len(research_results)} 个子问题进行研究，共检索到 {total_papers} 篇相关论文。"

        # 简单结论
        all_points = []
        for result in research_results:
            all_points.extend(result.key_points[:2])
        conclusion = "综合研究发现：" + "；".join(all_points[:5]) + "。"

        return ResearchReport(
            title=f"关于「{decomposition.original_query}」的研究报告",
            overview=overview,
            sections=sections,
            conclusion=conclusion,
            sources=all_sources,
            metadata={
                "original_query": decomposition.original_query,
                "query_type": decomposition.query_type,
                "sub_questions_count": len(decomposition.sub_questions),
                "total_papers": total_papers,
                "generated_at": datetime.now().isoformat()
            }
        )

    def _empty_report(self, query: str) -> ResearchReport:
        """空报告"""
        return ResearchReport(
            title=f"关于「{query}」的研究报告",
            overview="未能完成研究，请稍后重试。",
            sections=[],
            conclusion="",
            sources=[],
            metadata={
                "original_query": query,
                "error": "No research results"
            }
        )

    def format_as_markdown(self, report: ResearchReport) -> str:
        """
        将报告格式化为 Markdown

        Args:
            report: 研究报告

        Returns:
            str: Markdown 格式的报告
        """
        lines = []

        # 标题
        lines.append(f"# {report.title}")
        lines.append("")

        # 元数据
        meta = report.metadata
        lines.append(f"> 研究类型: {meta.get('query_type', 'N/A')} | "
                    f"子问题: {meta.get('sub_questions_count', 0)} 个 | "
                    f"论文: {meta.get('total_papers', 0)} 篇")
        lines.append("")

        # 概述
        lines.append("## 概述")
        lines.append("")
        lines.append(report.overview)
        lines.append("")

        # 核心要点
        if meta.get("key_takeaways"):
            lines.append("### 核心要点")
            lines.append("")
            for i, point in enumerate(meta["key_takeaways"], 1):
                lines.append(f"{i}. {point}")
            lines.append("")

        # 各章节
        for i, section in enumerate(report.sections, 1):
            heading = section.get("heading", f"部分 {i}")
            lines.append(f"## {i}. {heading}")
            lines.append("")
            lines.append(section.get("content", ""))
            lines.append("")

            if section.get("key_findings"):
                lines.append("**关键发现：**")
                for finding in section["key_findings"]:
                    lines.append(f"- {finding}")
                lines.append("")

        # 结论
        lines.append("## 结论")
        lines.append("")
        lines.append(report.conclusion)
        lines.append("")

        # 引用来源
        if report.sources:
            lines.append("## 参考来源")
            lines.append("")
            for i, src in enumerate(report.sources[:10], 1):
                title = src.get("title", "未知标题")
                year = src.get("year", "")
                url = src.get("url", "")
                source = src.get("source", "").upper()

                # 格式: [编号] **标题** (来源, 年份) [链接]
                line = f"**{i}. {title}**"
                meta_parts = []
                if source:
                    meta_parts.append(source)
                if year:
                    meta_parts.append(str(year))
                if meta_parts:
                    line += f" ({', '.join(meta_parts)})"
                if url:
                    line += f" → [查看论文]({url})"
                lines.append(line)
                lines.append("")
            lines.append("")

        return "\n".join(lines)


# 测试代码
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from .decomposer import SubQuestion

    load_dotenv()

    # 模拟数据
    decomposition = DecompositionResult(
        original_query="对比 Transformer 和 RNN 在 NLP 中的应用",
        query_type="comparison",
        sub_questions=[],
        research_strategy="分别研究两种架构，再进行综合对比"
    )

    research_results = [
        ResearchResult(
            sub_question="Transformer 架构的核心原理和在 NLP 中的典型应用",
            purpose="了解 Transformer 基础",
            papers_found=10,
            compressed_findings="Transformer 架构基于自注意力机制，能够并行处理序列数据。在 NLP 领域，它已成为主流架构，BERT、GPT 等模型都基于此。",
            key_points=["自注意力机制", "并行计算", "预训练-微调范式"],
            sources=[{"title": "Attention Is All You Need", "year": 2017, "url": "https://arxiv.org/abs/1706.03762", "source": "arxiv"}]
        ),
        ResearchResult(
            sub_question="RNN/LSTM 架构的核心原理和在 NLP 中的典型应用",
            purpose="了解 RNN 基础",
            papers_found=8,
            compressed_findings="RNN 通过循环结构处理序列数据，LSTM 解决了长期依赖问题。曾是 NLP 的主流选择，但计算效率较低。",
            key_points=["循环结构", "LSTM门控机制", "序列处理"],
            sources=[{"title": "Long Short-Term Memory", "year": 1997, "url": "", "source": "openalex"}]
        )
    ]

    generator = ReportGenerator(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY")
    )

    print("=" * 60)
    print("报告生成器测试")
    print("=" * 60)

    report = generator.generate(decomposition, research_results)

    print("\n生成的 Markdown 报告:\n")
    print(generator.format_as_markdown(report))
