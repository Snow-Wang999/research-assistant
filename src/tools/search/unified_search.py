"""统一搜索器 - 整合多个搜索源"""
from typing import List, Optional, Literal
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from .semantic_scholar import SemanticScholarSearch, Paper
from .arxiv_search import ArxivSearch
from .openalex_search import OpenAlexSearch


@dataclass
class SearchResult:
    """统一搜索结果"""
    papers: List[Paper]
    sources_used: List[str]
    total_count: int


class UnifiedSearch:
    """
    统一搜索器

    整合多个论文搜索源，支持并行搜索和结果合并。

    默认使用 arXiv + OpenAlex（替代 Semantic Scholar，因后者有严格的速率限制）
    """

    def __init__(
        self,
        semantic_scholar_key: Optional[str] = None,
        openalex_email: Optional[str] = None,
        sources: List[str] = None
    ):
        """
        初始化统一搜索器

        Args:
            semantic_scholar_key: Semantic Scholar API Key（可选）
            openalex_email: OpenAlex 邮箱（可选，提高速率限制）
            sources: 要使用的搜索源列表，默认["arxiv", "openalex"]
        """
        # 默认使用 arXiv + OpenAlex（OpenAlex 替代 Semantic Scholar）
        self.sources = sources or ["arxiv", "openalex"]

        # 初始化各搜索源
        self.searchers = {}
        if "semantic_scholar" in self.sources:
            self.searchers["semantic_scholar"] = SemanticScholarSearch(api_key=semantic_scholar_key)
        if "arxiv" in self.sources:
            self.searchers["arxiv"] = ArxivSearch()
        if "openalex" in self.sources:
            self.searchers["openalex"] = OpenAlexSearch(email=openalex_email)

    def search(
        self,
        query: str,
        limit: int = 10,
        sources: List[str] = None,
        parallel: bool = True
    ) -> SearchResult:
        """
        统一搜索

        Args:
            query: 搜索关键词
            limit: 每个源返回的最大数量
            sources: 使用的搜索源（默认使用所有已配置的源）
            parallel: 是否并行搜索

        Returns:
            SearchResult: 合并后的搜索结果
        """
        sources_to_use = sources or list(self.searchers.keys())
        all_papers = []
        sources_used = []

        if parallel and len(sources_to_use) > 1:
            # 并行搜索
            with ThreadPoolExecutor(max_workers=len(sources_to_use)) as executor:
                futures = {
                    executor.submit(self._search_single, source, query, limit): source
                    for source in sources_to_use
                    if source in self.searchers
                }

                for future in as_completed(futures):
                    source = futures[future]
                    try:
                        papers = future.result()
                        all_papers.extend(papers)
                        if papers:
                            sources_used.append(source)
                    except Exception as e:
                        print(f"{source} 搜索出错: {e}")
        else:
            # 串行搜索
            for source in sources_to_use:
                if source in self.searchers:
                    papers = self._search_single(source, query, limit)
                    all_papers.extend(papers)
                    if papers:
                        sources_used.append(source)

        # 去重（基于标题相似度）
        unique_papers = self._deduplicate(all_papers)

        # 分组排序：arXiv（时效性）在前，OpenAlex（经典高引用）在后
        # 每组内部：arXiv按时间（默认），OpenAlex按引用数
        sorted_papers = self._group_by_source(unique_papers)

        return SearchResult(
            papers=sorted_papers[:limit * 2],  # 返回更多结果
            sources_used=sources_used,
            total_count=len(unique_papers)
        )

    def _search_single(self, source: str, query: str, limit: int) -> List[Paper]:
        """单个源搜索"""
        searcher = self.searchers.get(source)
        if searcher:
            return searcher.search(query, limit=limit)
        return []

    def _deduplicate(self, papers: List[Paper]) -> List[Paper]:
        """
        论文去重（基于标题）

        简单实现：标题完全相同视为重复
        TODO: 后续可用模糊匹配或论文ID
        """
        seen_titles = set()
        unique = []

        for paper in papers:
            title_lower = paper.title.lower().strip()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                unique.append(paper)

        return unique

    def _group_by_source(self, papers: List[Paper]) -> List[Paper]:
        """
        按来源分组排序

        顺序：arXiv（最新）→ OpenAlex（高引用+时效性）→ 其他
        每组内部排序：
        - arXiv: 保持原顺序（API默认按时间）
        - OpenAlex: 综合评分 = 引用数 + 时效性加成
        """
        from datetime import datetime
        current_year = datetime.now().year

        # 按来源分组
        arxiv_papers = []
        openalex_papers = []
        other_papers = []

        for paper in papers:
            if paper.source == "arxiv":
                arxiv_papers.append(paper)
            elif paper.source == "openalex":
                openalex_papers.append(paper)
            else:
                other_papers.append(paper)

        # OpenAlex 综合排序：引用数 + 时效性
        # 评分 = 引用数 + (年份越新加分越多)
        # 近3年的论文获得额外加分
        def openalex_score(paper):
            citations = paper.citation_count if paper.citation_count else 0
            year = paper.year if paper.year else 2000

            # 时效性加成：每接近当前年份1年，加500分
            # 例如：2024年论文加2000分，2023年加1500分，2020年加0分
            years_ago = current_year - year
            recency_bonus = max(0, (4 - years_ago) * 500)  # 近4年内有加成

            return citations + recency_bonus

        openalex_papers.sort(key=openalex_score, reverse=True)

        # 合并：arXiv在前，OpenAlex在后
        return arxiv_papers + openalex_papers + other_papers

    def search_multi_keywords(
        self,
        keywords: List[str],
        limit_per_keyword: int = 5,
        total_limit: int = 10
    ) -> SearchResult:
        """
        多关键词搜索

        用多组关键词分别搜索，合并去重结果。

        Args:
            keywords: 多组搜索关键词
            limit_per_keyword: 每组关键词每个源返回的数量
            total_limit: 每个源最终返回的总数量

        Returns:
            SearchResult: 合并去重后的结果
        """
        if not keywords:
            return SearchResult(papers=[], sources_used=[], total_count=0)

        all_papers = []
        sources_used = set()

        # 并行搜索所有关键词
        with ThreadPoolExecutor(max_workers=min(len(keywords) * 2, 8)) as executor:
            futures = []
            for kw in keywords:
                for source in self.searchers.keys():
                    futures.append(
                        executor.submit(self._search_single, source, kw, limit_per_keyword)
                    )

            for future in as_completed(futures):
                try:
                    papers = future.result()
                    if papers:
                        all_papers.extend(papers)
                        sources_used.add(papers[0].source)
                except Exception as e:
                    print(f"多关键词搜索出错: {e}")

        # 去重
        unique_papers = self._deduplicate(all_papers)

        # 分组排序
        sorted_papers = self._group_by_source(unique_papers)

        # 限制每个源的数量
        arxiv_papers = [p for p in sorted_papers if p.source == "arxiv"][:total_limit]
        openalex_papers = [p for p in sorted_papers if p.source == "openalex"][:total_limit]
        final_papers = arxiv_papers + openalex_papers

        print(f"[多关键词搜索] 关键词数: {len(keywords)}, 去重后: {len(unique_papers)}, 最终: {len(final_papers)}")

        return SearchResult(
            papers=final_papers,
            sources_used=list(sources_used),
            total_count=len(unique_papers)
        )

    def search_arxiv_only(self, query: str, limit: int = 10) -> List[Paper]:
        """仅搜索arXiv"""
        return self._search_single("arxiv", query, limit)

    def search_semantic_scholar_only(self, query: str, limit: int = 10) -> List[Paper]:
        """仅搜索Semantic Scholar"""
        return self._search_single("semantic_scholar", query, limit)

    def search_openalex_only(self, query: str, limit: int = 10) -> List[Paper]:
        """仅搜索OpenAlex"""
        return self._search_single("openalex", query, limit)


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("统一搜索器测试")
    print("=" * 60)

    searcher = UnifiedSearch()

    result = searcher.search("large language model GPT", limit=5)

    print(f"\n使用的搜索源: {result.sources_used}")
    print(f"找到论文总数: {result.total_count}")
    print(f"返回论文数: {len(result.papers)}")
    print("\n" + "-" * 60)

    for i, paper in enumerate(result.papers[:5], 1):
        print(f"\n[{i}] {paper.title}")
        print(f"    来源: {paper.source}")
        print(f"    作者: {', '.join(paper.authors[:3])}")
        print(f"    年份: {paper.year}")
        if paper.citation_count:
            print(f"    引用: {paper.citation_count}")
