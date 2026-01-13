"""科研助手主入口"""
import sys
from pathlib import Path
from typing import Optional

# 添加src目录到路径
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from tools.search import UnifiedSearch
from tools.query_analyzer import QueryAnalyzer
from tools.abstract_summarizer import AbstractSummarizer
from tools.reading_guide import ReadingGuide
from utils.config import config


class ResearchAssistant:
    """科研助手主类"""

    def __init__(self, semantic_scholar_key: Optional[str] = None):
        # 使用统一搜索器（整合arXiv + OpenAlex）
        ss_key = semantic_scholar_key or config.SEMANTIC_SCHOLAR_API_KEY
        self.searcher = UnifiedSearch(semantic_scholar_key=ss_key)

        # 初始化查询分析器和摘要总结器
        translator_config = config.get_translator_config()
        deepseek_key = translator_config.get("deepseek_api_key")

        if deepseek_key:
            self.analyzer = QueryAnalyzer(deepseek_api_key=deepseek_key)
            self.summarizer = AbstractSummarizer(deepseek_api_key=deepseek_key)
            self.reading_guide = ReadingGuide(deepseek_api_key=deepseek_key)
        else:
            self.analyzer = QueryAnalyzer()  # 会使用回退方案
            self.summarizer = None
            self.reading_guide = ReadingGuide()  # 使用回退方案
            print("提示: 未配置 DEEPSEEK_API_KEY，将使用简单模式")

    def process_query(self, query: str, mode: str = "auto") -> dict:
        """
        处理用户查询

        Args:
            query: 用户查询
            mode: 搜索模式 "auto" | "simple" | "deep_research"
                  auto: 由 QueryAnalyzer 建议
                  simple: 快速搜索
                  deep_research: 深度研究（暂未实现完整功能）

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
            return self._handle_deep_research(query, analysis)

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

    def _handle_deep_research(self, original_query: str, analysis) -> dict:
        """
        处理深度研究查询

        TODO: v0.3.0 实现完整的深度研究功能
        - 子问题分解
        - 多轮迭代搜索
        - 综合分析报告
        """
        # 当前：使用更多的搜索结果
        result = self.searcher.search_multi_keywords(
            keywords=analysis.keywords,
            limit_per_keyword=5,
            total_limit=10  # Deep Research 返回更多结果
        )

        # 转换为字典格式
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

        # LLM总结摘要
        if self.summarizer and all_papers:
            all_papers = self.summarizer.summarize_batch(all_papers)
            arxiv_papers = [p for p in all_papers if p.get('source') == 'arxiv']
            openalex_papers = [p for p in all_papers if p.get('source') == 'openalex']

        # 生成阅读导航
        reading_guide = self.reading_guide.generate(original_query, all_papers)

        return {
            "mode": "deep_research",
            "query": original_query,
            "intent": analysis.intent,
            "keywords": analysis.keywords,
            "sources": result.sources_used,
            "total_found": result.total_count,
            "arxiv_papers": arxiv_papers,
            "openalex_papers": openalex_papers,
            "papers": all_papers,
            "reading_guide": reading_guide,
            # TODO: 添加深度分析报告
            "report": None,
        }


def main():
    """命令行入口"""
    print("=" * 50)
    print("科研助手 v0.2.0")
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
            print(f"找到 {len(result['papers'])} 篇相关论文:\n")

            for i, paper in enumerate(result["papers"], 1):
                source_tag = f"[{paper.get('source', 'unknown')}]"
                print(f"[{i}] {source_tag} {paper['title']}")
                if paper.get('title_cn'):
                    print(f"    📖 {paper['title_cn']}")
                print(f"    作者: {', '.join(paper['authors'])}")
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
