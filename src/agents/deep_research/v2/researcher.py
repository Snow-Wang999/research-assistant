"""V2 Researcher - 研究员子 Agent

作为 Tool 被 Supervisor 调用，执行：
1. 论文搜索
2. 相关性筛选
3. 内容压缩
4. 返回 CompressedResearch

关键设计：
- 独立上下文，不污染 Supervisor
- 返回压缩结果，不返回完整论文
- 原始数据卸载到 raw_notes
"""
import json
import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tools.search import UnifiedSearch
from utils.llm_client import QwenClient
from utils.logger import get_agent_logger

from .tools import ConductResearch, SearchStrategy
from .prompts import build_researcher_prompt

log = get_agent_logger()


@dataclass
class CompressedResearch:
    """压缩后的研究结果（返回给 Supervisor）"""
    topic: str                      # 研究主题
    findings: str                   # 核心发现
    key_points: List[str]           # 关键要点
    sources: List[Dict]             # 来源论文（精简信息）
    gaps: Optional[str] = None      # 研究缺口（可选）
    papers_searched: int = 0        # 搜索到的论文数
    papers_selected: int = 0        # 筛选出的论文数

    def to_message(self) -> str:
        """转换为 Supervisor 可读的消息"""
        sources_str = "\n".join([
            f"  - [{s.get('year', 'N/A')}] {s.get('title', 'Unknown')[:60]}..."
            for s in self.sources[:5]
        ])

        msg = f"""### 研究结果：{self.topic}

**核心发现：**
{self.findings}

**关键要点：**
{chr(10).join([f"- {p}" for p in self.key_points])}

**来源论文（{self.papers_selected}/{self.papers_searched} 篇相关）：**
{sources_str}
"""
        if self.gaps:
            msg += f"\n**研究缺口：** {self.gaps}"

        return msg


@dataclass
class RawResearchData:
    """原始研究数据（用于卸载）"""
    topic: str
    keywords: List[str]
    papers: List[Dict]              # 完整论文信息
    llm_response: Optional[str] = None  # LLM 原始响应
    created_at: datetime = field(default_factory=datetime.now)


class Researcher:
    """
    研究员 Agent

    作为 Tool 被 Supervisor 调用，执行独立的研究任务。

    使用方式：
    ```python
    researcher = Researcher(qwen_api_key="...")
    task = ConductResearch(topic="...", search_keywords=["..."])
    result, raw_data = researcher.research(task, round_number=1)
    ```
    """

    def __init__(
        self,
        qwen_api_key: Optional[str] = None,
        searcher: Optional[UnifiedSearch] = None,
        papers_per_search: int = 15
    ):
        """
        初始化研究员

        Args:
            qwen_api_key: 通义千问 API Key
            searcher: 统一搜索器（可共享）
            papers_per_search: 每次搜索的论文数量
        """
        self.llm_client = QwenClient(api_key=qwen_api_key) if qwen_api_key else None
        self.searcher = searcher or UnifiedSearch()
        self.papers_per_search = papers_per_search

    def research(
        self,
        task: ConductResearch,
        round_number: int = 1
    ) -> tuple[CompressedResearch, RawResearchData]:
        """
        执行研究任务

        Args:
            task: 研究任务
            round_number: 当前轮数

        Returns:
            (CompressedResearch, RawResearchData): 压缩结果和原始数据
        """
        log.info(f"[Researcher] 开始研究: {task.topic}")
        log.debug(f"[Researcher] 关键词: {task.search_keywords}, 策略: {task.strategy}")

        # 1. 搜索论文
        papers = self._search_papers(task)

        # 2. 创建原始数据记录
        raw_data = RawResearchData(
            topic=task.topic,
            keywords=task.search_keywords,
            papers=papers
        )

        if not papers:
            log.warning(f"[Researcher] 未找到相关论文: {task.topic}")
            return self._empty_result(task), raw_data

        # 3. 使用 LLM 压缩
        if self.llm_client:
            result = self._compress_with_llm(task, papers, raw_data)
        else:
            result = self._compress_fallback(task, papers)

        log.info(f"[Researcher] 完成研究: {task.topic}, 筛选 {result.papers_selected}/{result.papers_searched} 篇")
        return result, raw_data

    def _search_papers(self, task: ConductResearch) -> List[Dict]:
        """搜索论文"""
        all_papers = []

        # 根据策略调整搜索量
        limit = self.papers_per_search
        if task.strategy == SearchStrategy.FOCUSED:
            limit = self.papers_per_search // 2  # 聚焦搜索减少数量
        elif task.strategy == SearchStrategy.COMPARISON:
            limit = self.papers_per_search  # 对比搜索保持数量

        # 使用多个关键词搜索
        for keyword in task.search_keywords[:3]:
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
                        "citation_count": paper.citation_count,
                        "arxiv_id": getattr(paper, 'arxiv_id', None)
                    }
                    all_papers.append(paper_dict)
            except Exception as e:
                log.error(f"[Researcher] 搜索 '{keyword}' 出错: {e}")

        # 去重
        seen_titles = set()
        unique_papers = []
        for p in all_papers:
            title_lower = p["title"].lower().strip()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                unique_papers.append(p)

        return unique_papers

    def _compress_with_llm(
        self,
        task: ConductResearch,
        papers: List[Dict],
        raw_data: RawResearchData
    ) -> CompressedResearch:
        """使用 LLM 压缩论文"""
        try:
            # 构建 Prompt
            prompt = build_researcher_prompt(
                topic=task.topic,
                keywords=task.search_keywords,
                papers=papers,
                focus_points=task.focus_points
            )

            log.debug(f"[Researcher] 调用 LLM 压缩, prompt 长度: {len(prompt)}")

            # 调用 LLM
            content = self.llm_client.chat(
                prompt=prompt,
                task_type="compress",
                max_tokens=1500,
                temperature=0.3,
                timeout=30.0
            )

            # 保存原始响应
            raw_data.llm_response = content

            # 解析响应
            parsed = self._parse_response(content)

            if parsed:
                # 构建来源信息
                sources = self._extract_sources(parsed.get("relevant_papers", []), papers)

                return CompressedResearch(
                    topic=task.topic,
                    findings=parsed.get("findings", "无法提取发现"),
                    key_points=parsed.get("key_points", []),
                    sources=sources,
                    gaps=parsed.get("gaps"),
                    papers_searched=len(papers),
                    papers_selected=len(sources)
                )

        except Exception as e:
            log.error(f"[Researcher] LLM 压缩出错: {e}")

        # 回退方案
        return self._compress_fallback(task, papers)

    def _parse_response(self, content: str) -> Optional[Dict]:
        """解析 LLM 响应"""
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 块
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取花括号内容
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _extract_sources(
        self,
        relevant_papers: List[Dict],
        all_papers: List[Dict]
    ) -> List[Dict]:
        """提取来源论文信息"""
        sources = []

        for rp in relevant_papers:
            rp_title = rp.get("title", "").lower().strip()

            # 在原始论文中查找匹配
            for p in all_papers:
                p_title = p.get("title", "").lower().strip()

                # 模糊匹配
                if rp_title in p_title or p_title in rp_title:
                    sources.append({
                        "title": p["title"],
                        "authors": p.get("authors", []),
                        "year": p.get("year"),
                        "url": p.get("url"),
                        "source": p.get("source"),
                        "citation_count": p.get("citation_count"),
                        "abstract": p.get("abstract", ""),  # 保留摘要
                        "key_contribution": rp.get("key_contribution", "")
                    })
                    break

        # 确保来源平衡：检查是否有 arXiv 论文
        arxiv_in_sources = [s for s in sources if s.get("source") == "arxiv"]
        if not arxiv_in_sources and len(sources) < 5:
            # 从原始列表补充 arXiv 论文
            arxiv_papers = [p for p in all_papers if p.get("source") == "arxiv"]
            arxiv_papers.sort(key=lambda x: x.get("year", 0) or 0, reverse=True)
            for p in arxiv_papers[:2]:
                if p["title"] not in [s["title"] for s in sources]:
                    sources.append({
                        "title": p["title"],
                        "authors": p.get("authors", []),
                        "year": p.get("year"),
                        "url": p.get("url"),
                        "source": p.get("source"),
                        "citation_count": p.get("citation_count"),
                        "abstract": p.get("abstract", ""),  # 保留摘要
                        "key_contribution": "最新研究（补充）"
                    })

        return sources

    def _compress_fallback(
        self,
        task: ConductResearch,
        papers: List[Dict]
    ) -> CompressedResearch:
        """回退方案：基于摘要的简单压缩"""
        log.info("[Researcher] 使用回退方案（摘要提取）")

        # 按引用数排序
        sorted_papers = sorted(
            papers,
            key=lambda x: (x.get("citation_count", 0) or 0, x.get("year", 0) or 0),
            reverse=True
        )

        # 提取关键发现
        findings_parts = []
        key_points = []

        for i, p in enumerate(sorted_papers[:5], 1):
            abstract = p.get("abstract", "")
            if not abstract:
                continue

            first_sentence = abstract.split('.')[0].strip()
            if len(first_sentence) > 20:
                findings_parts.append(f"{p['title'][:40]}...: {first_sentence}.")
                key_points.append(f"[{p.get('year', 'N/A')}] {abstract[:60]}...")

        findings = f"基于 {len(papers)} 篇论文: " + " ".join(findings_parts[:3])

        # 提取来源
        sources = []
        for p in sorted_papers[:5]:
            sources.append({
                "title": p["title"],
                "authors": p.get("authors", []),
                "year": p.get("year"),
                "url": p.get("url"),
                "source": p.get("source"),
                "citation_count": p.get("citation_count"),
                "key_contribution": ""
            })

        return CompressedResearch(
            topic=task.topic,
            findings=findings,
            key_points=key_points[:3] if key_points else ["无法提取要点"],
            sources=sources,
            papers_searched=len(papers),
            papers_selected=len(sources)
        )

    def _empty_result(self, task: ConductResearch) -> CompressedResearch:
        """空结果"""
        return CompressedResearch(
            topic=task.topic,
            findings="未找到相关论文。可能需要调整搜索关键词。",
            key_points=["无搜索结果"],
            sources=[],
            gaps="需要更换关键词重新搜索",
            papers_searched=0,
            papers_selected=0
        )


# 测试代码
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    print("=" * 60)
    print("V2 Researcher 测试")
    print("=" * 60)

    # 创建研究员
    researcher = Researcher(
        qwen_api_key=os.getenv("QWEN_API_KEY")
    )

    # 创建研究任务
    task = ConductResearch(
        topic="Transformer 自注意力机制的原理和应用",
        search_keywords=["Transformer self-attention", "attention mechanism NLP"],
        strategy=SearchStrategy.FOCUSED,
        focus_points=["并行计算", "位置编码"]
    )

    # 执行研究
    result, raw_data = researcher.research(task, round_number=1)

    print(f"\n{result.to_message()}")
    print(f"\n--- 原始数据 ---")
    print(f"搜索到: {len(raw_data.papers)} 篇论文")
    print(f"关键词: {raw_data.keywords}")
