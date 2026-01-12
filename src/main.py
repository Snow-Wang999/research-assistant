"""科研助手主入口"""
import sys
from pathlib import Path
from typing import Optional

# 添加src目录到路径
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from agents import IntentRouter
from tools.search import UnifiedSearch
from tools.query_translator import QueryTranslator
from tools.abstract_summarizer import AbstractSummarizer
from utils.config import config


class ResearchAssistant:
    """科研助手主类"""

    def __init__(self, semantic_scholar_key: Optional[str] = None):
        self.router = IntentRouter()

        # 使用统一搜索器（整合arXiv + OpenAlex）
        ss_key = semantic_scholar_key or config.SEMANTIC_SCHOLAR_API_KEY
        self.searcher = UnifiedSearch(semantic_scholar_key=ss_key)

        # 初始化查询翻译器
        translator_config = config.get_translator_config()
        if translator_config["deepseek_api_key"] or translator_config["qwen_api_key"]:
            self.translator = QueryTranslator(**translator_config)
            # 初始化摘要总结器（复用DeepSeek API Key）
            self.summarizer = AbstractSummarizer(
                deepseek_api_key=translator_config["deepseek_api_key"]
            )
        else:
            self.translator = None
            self.summarizer = None
            print("提示: 未配置 LLM API Key，中文查询将直接使用原文搜索")

    def _translate_query(self, query: str) -> str:
        """翻译查询为英文搜索关键词"""
        if self.translator:
            return self.translator.translate(query)
        return query

    def process_query(self, query: str) -> dict:
        """处理用户查询"""
        # 1. 路由决策
        mode = self.router.route(query)

        # 2. 翻译查询（如果是中文）
        search_query = self._translate_query(query)

        # 3. 根据模式执行
        if mode == "simple":
            return self._handle_simple_query(query, search_query)
        else:
            return self._handle_deep_research(query, search_query)

    def _handle_simple_query(self, original_query: str, search_query: str) -> dict:
        """处理简单查询（RAG模式）"""
        # 搜索论文（每个源5篇，共10篇）
        result = self.searcher.search(search_query, limit=5)

        # 按来源分组，保留完整摘要
        arxiv_papers = []
        openalex_papers = []
        for p in result.papers:
            paper_dict = {
                "title": p.title,
                "authors": p.authors[:3],
                "year": p.year,
                "citation_count": p.citation_count,
                "abstract": p.abstract,  # 保留完整摘要
                "url": p.url,
                "source": p.source,
            }
            if p.source == "arxiv":
                arxiv_papers.append(paper_dict)
            else:
                openalex_papers.append(paper_dict)

        # 限制数量
        arxiv_papers = arxiv_papers[:5]
        openalex_papers = openalex_papers[:5]
        all_papers = arxiv_papers + openalex_papers

        # LLM总结摘要（批量并行处理）
        if self.summarizer:
            all_papers = self.summarizer.summarize_batch(all_papers)
            # 重新分组
            arxiv_papers = [p for p in all_papers if p.get('source') == 'arxiv']
            openalex_papers = [p for p in all_papers if p.get('source') == 'openalex']

        return {
            "mode": "simple",
            "query": original_query,
            "search_query": search_query,
            "sources": result.sources_used,
            "arxiv_papers": arxiv_papers,
            "openalex_papers": openalex_papers,
            "papers": all_papers,
        }

    def _handle_deep_research(self, original_query: str, search_query: str) -> dict:
        """处理深度研究查询"""
        # MVP阶段：每个源5篇，共10篇
        result = self.searcher.search(search_query, limit=5)

        # 按来源分组，保留完整摘要
        arxiv_papers = []
        openalex_papers = []
        for p in result.papers:
            paper_dict = {
                "title": p.title,
                "authors": p.authors[:3],
                "year": p.year,
                "citation_count": p.citation_count,
                "abstract": p.abstract,  # 保留完整摘要
                "url": p.url,
                "source": p.source,
            }
            if p.source == "arxiv":
                arxiv_papers.append(paper_dict)
            else:
                openalex_papers.append(paper_dict)

        # 限制数量
        arxiv_papers = arxiv_papers[:5]
        openalex_papers = openalex_papers[:5]
        all_papers = arxiv_papers + openalex_papers

        # LLM总结摘要（批量并行处理）
        if self.summarizer:
            all_papers = self.summarizer.summarize_batch(all_papers)
            arxiv_papers = [p for p in all_papers if p.get('source') == 'arxiv']
            openalex_papers = [p for p in all_papers if p.get('source') == 'openalex']

        return {
            "mode": "deep_research",
            "query": original_query,
            "search_query": search_query,
            "sources": result.sources_used,
            "total_found": result.total_count,
            "arxiv_papers": arxiv_papers,
            "openalex_papers": openalex_papers,
            "papers": all_papers,
        }


def main():
    """命令行入口"""
    print("=" * 50)
    print("科研助手 v0.1.0 (MVP)")
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

            print(f"\n正在搜索: {query}")
            print("（使用 arXiv + Semantic Scholar 并行搜索）\n")

            result = assistant.process_query(query)

            print(f"模式: {result['mode']}")
            print(f"搜索源: {', '.join(result.get('sources', []))}")
            print(f"找到 {len(result['papers'])} 篇相关论文:\n")

            for i, paper in enumerate(result["papers"], 1):
                source_tag = f"[{paper.get('source', 'unknown')}]"
                print(f"[{i}] {source_tag} {paper['title']}")
                print(f"    作者: {', '.join(paper['authors'])}")
                print(f"    年份: {paper.get('year', 'N/A')}")
                if paper.get('citation_count'):
                    print(f"    引用: {paper['citation_count']}")
                print(f"    链接: {paper['url']}")
                print()

        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"处理出错: {e}")


if __name__ == "__main__":
    main()
