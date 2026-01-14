"""科研助手主入口"""
import sys
from pathlib import Path
from typing import Optional, Callable

# 添加src目录到路径
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from tools.search import UnifiedSearch
from tools.query_analyzer import QueryAnalyzer
from tools.abstract_summarizer import AbstractSummarizer
from tools.reading_guide import ReadingGuide
from agents.deep_research import DeepResearchOrchestrator
from utils.config import config


class ResearchAssistant:
    """科研助手主类"""

    def __init__(
        self,
        semantic_scholar_key: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ):
        """
        初始化科研助手

        Args:
            semantic_scholar_key: Semantic Scholar API Key（可选）
            progress_callback: 进度回调函数，用于 UI 显示进度
        """
        # 使用统一搜索器（整合arXiv + OpenAlex）
        ss_key = semantic_scholar_key or config.SEMANTIC_SCHOLAR_API_KEY
        self.searcher = UnifiedSearch(semantic_scholar_key=ss_key)
        self.progress_callback = progress_callback

        # 初始化查询分析器和摘要总结器
        translator_config = config.get_translator_config()
        self.deepseek_key = translator_config.get("deepseek_api_key")

        if self.deepseek_key:
            self.analyzer = QueryAnalyzer(deepseek_api_key=self.deepseek_key)
            self.summarizer = AbstractSummarizer(deepseek_api_key=self.deepseek_key)
            self.reading_guide = ReadingGuide(deepseek_api_key=self.deepseek_key)
            # 深度研究协调器
            self.deep_research = DeepResearchOrchestrator(
                deepseek_api_key=self.deepseek_key,
                progress_callback=progress_callback
            )
        else:
            self.analyzer = QueryAnalyzer()  # 会使用回退方案
            self.summarizer = None
            self.reading_guide = ReadingGuide()  # 使用回退方案
            self.deep_research = DeepResearchOrchestrator()  # 使用回退方案
            print("提示: 未配置 DEEPSEEK_API_KEY，将使用简单模式")

    def process_query(self, query: str, mode: str = "auto", use_fulltext: bool = False) -> dict:
        """
        处理用户查询

        Args:
            query: 用户查询
            mode: 搜索模式 "auto" | "simple" | "deep_research"
                  auto: 由 QueryAnalyzer 建议
                  simple: 快速搜索
                  deep_research: 深度研究
            use_fulltext: 是否使用全文研究（仅深度研究模式有效，v0.4.0）

        Returns:
            搜索结果字典
        """
        # 1. 分析查询，生成多组关键词
        analysis = self.analyzer.analyze(query)

        # 2. 确定模式
        if mode == "auto":
            mode = analysis.suggested_mode

        # 3. 根据模式执行
        if mode == "simple":
            return self._handle_simple_query(query, analysis)
        else:
            return self._handle_deep_research(query, analysis, use_fulltext=use_fulltext)

    def _handle_simple_query(self, original_query: str, analysis) -> dict:
        """处理快速搜索"""
        # 使用多关键词搜索
        result = self.searcher.search_multi_keywords(
            keywords=analysis.keywords,
            limit_per_keyword=3,
            total_limit=5
        )

        # 转换为字典格式，按来源分组
        arxiv_papers = []
        openalex_papers = []
        for p in result.papers:
            paper_dict = {
                "title": p.title,
                "authors": p.authors[:3],
                "year": p.year,
                "citation_count": p.citation_count,
                "abstract": p.abstract,
                "url": p.url,
                "source": p.source,
            }
            if p.source == "arxiv":
                arxiv_papers.append(paper_dict)
            else:
                openalex_papers.append(paper_dict)

        all_papers = arxiv_papers + openalex_papers

        # LLM总结摘要（批量并行处理）
        if self.summarizer and all_papers:
            all_papers = self.summarizer.summarize_batch(all_papers)
            arxiv_papers = [p for p in all_papers if p.get('source') == 'arxiv']
            openalex_papers = [p for p in all_papers if p.get('source') == 'openalex']

        # 生成阅读导航
        reading_guide = self.reading_guide.generate(original_query, all_papers)

        return {
            "mode": "simple",
            "query": original_query,
            "intent": analysis.intent,
            "keywords": analysis.keywords,
            "suggested_mode": analysis.suggested_mode,
            "sources": result.sources_used,
            "total_found": result.total_count,
            "arxiv_papers": arxiv_papers,
            "openalex_papers": openalex_papers,
            "papers": all_papers,
            "reading_guide": reading_guide,
        }

    def _handle_deep_research(self, original_query: str, analysis, use_fulltext: bool = False) -> dict:
        """
        处理深度研究查询

        v0.3.0 实现：
        - 子问题分解
        - 并行搜索研究
        - 综合分析报告

        v0.4.0 新增：
        - 支持全文研究模式（下载 PDF）
        """
        # 根据 use_fulltext 创建配置
        from agents.deep_research import DeepResearchConfig
        config = DeepResearchConfig(use_fulltext=use_fulltext)

        # 创建协调器实例（使用指定配置）
        orchestrator = DeepResearchOrchestrator(
            deepseek_api_key=self.deepseek_key,
            config=config,
            progress_callback=self.progress_callback
        )

        # 执行深度研究
        deep_result = orchestrator.run(original_query)

        # 收集所有论文（从各子问题的研究结果中提取）
        all_papers = []
        arxiv_papers = []
        openalex_papers = []

        seen_titles = set()  # 去重
        for research_result in deep_result.research_results:
            for src in research_result.sources:
                title = src.get("title", "")
                if title.lower() in seen_titles:
                    continue
                seen_titles.add(title.lower())

                paper_dict = {
                    "title": title,
                    "authors": src.get("authors", []),
                    "year": src.get("year"),
                    "citation_count": src.get("citation_count"),
                    "abstract": src.get("abstract", ""),
                    "url": src.get("url", ""),
                    "source": src.get("source", "unknown"),
                    "relevance": src.get("relevance", ""),
                }
                all_papers.append(paper_dict)

                if src.get("source") == "arxiv":
                    arxiv_papers.append(paper_dict)
                else:
                    openalex_papers.append(paper_dict)

        # 深度研究模式不需要额外的摘要总结，报告已包含分析
        # 只截取原始摘要的前150字作为简要说明
        for paper in all_papers:
            abstract = paper.get("abstract", "")
            if abstract and len(abstract) > 150:
                paper["summary"] = abstract[:150] + "..."
            elif abstract:
                paper["summary"] = abstract

        # 生成阅读导航（基于报告中的论文）
        reading_guide = self.reading_guide.generate(original_query, all_papers)

        # 获取报告中的参考来源（与报告引用编号一致）
        report_sources = []
        if deep_result.report and deep_result.report.sources:
            for src in deep_result.report.sources:
                report_sources.append({
                    "title": src.get("title", ""),
                    "authors": src.get("authors", []),
                    "year": src.get("year"),
                    "citation_count": src.get("citation_count"),
                    "abstract": src.get("abstract", ""),
                    "url": src.get("url", ""),
                    "source": src.get("source", "unknown"),
                    "relevance": src.get("relevance", ""),
                    "summary": src.get("abstract", "")[:150] + "..." if src.get("abstract", "") and len(src.get("abstract", "")) > 150 else src.get("abstract", ""),
                })

        return {
            "mode": "deep_research",
            "query": original_query,
            "intent": analysis.intent,
            "keywords": analysis.keywords,
            "sources": ["arxiv", "openalex"],
            "total_found": deep_result.metadata.get("total_papers", 0),
            "arxiv_papers": arxiv_papers,
            "openalex_papers": openalex_papers,
            "papers": all_papers,
            "reading_guide": reading_guide,
            # 深度研究特有内容
            "report": deep_result.report_markdown,
            "report_sources": report_sources,  # 与报告引用编号一致的参考来源
            "decomposition": {
                "query_type": deep_result.decomposition.query_type,
                "strategy": deep_result.decomposition.research_strategy,
                "sub_questions": [
                    {
                        "question": sq.question,
                        "purpose": sq.purpose,
                        "keywords": sq.search_keywords
                    }
                    for sq in deep_result.decomposition.sub_questions
                ]
            },
            "metadata": deep_result.metadata,
        }


def main():
    """命令行入口"""
    print("=" * 50)
    print("科研助手 v0.3.0")
    print("支持深度研究：子问题分解 + 并行搜索 + 研究报告")
    print("=" * 50)

    assistant = ResearchAssistant()

    while True:
        try:
            query = input("\n请输入研究问题 (输入 'quit' 退出): ").strip()

            if query.lower() in ["quit", "exit", "q"]:
                print("再见！")
                break

            if not query:
                continue

            print(f"\n正在分析: {query}")
            print("（使用 arXiv + OpenAlex 多关键词并行搜索）\n")

            result = assistant.process_query(query)

            print(f"意图: {result.get('intent', '')}")
            print(f"关键词: {result.get('keywords', [])}")
            print(f"模式: {result['mode']}")
            print(f"搜索源: {', '.join(result.get('sources', []))}")

            # 深度研究模式显示报告
            if result['mode'] == 'deep_research' and result.get('report'):
                print("\n" + "=" * 50)
                print("深度研究报告")
                print("=" * 50)
                print(result['report'])
            else:
                # 快速搜索模式显示论文列表
                print(f"找到 {len(result['papers'])} 篇相关论文:\n")

                for i, paper in enumerate(result["papers"], 1):
                    source_tag = f"[{paper.get('source', 'unknown')}]"
                    print(f"[{i}] {source_tag} {paper['title']}")
                    if paper.get('title_cn'):
                        print(f"    📖 {paper['title_cn']}")
                    authors = paper.get('authors', [])
                    if authors:
                        print(f"    作者: {', '.join(authors)}")
                    print(f"    年份: {paper.get('year', 'N/A')}")
                    if paper.get('citation_count'):
                        print(f"    引用: {paper['citation_count']}")
                    if paper.get('summary'):
                        print(f"    摘要: {paper['summary']}")
                    print(f"    链接: {paper['url']}")
                    print()

        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"处理出错: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
