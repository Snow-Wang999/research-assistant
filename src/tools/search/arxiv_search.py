"""arXiv 论文搜索"""
import arxiv
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Paper:
    """论文数据结构"""
    paper_id: str
    title: str
    authors: List[str]
    abstract: str
    url: str
    year: Optional[int] = None
    citation_count: Optional[int] = None
    source: str = "arxiv"


class ArxivSearch:
    """arXiv 论文搜索工具"""

    def __init__(self):
        self.client = arxiv.Client()

    def search(
        self,
        query: str,
        limit: int = 10,
        sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance
    ) -> List[Paper]:
        """
        搜索arXiv论文

        Args:
            query: 搜索关键词
            limit: 返回数量
            sort_by: 排序方式（Relevance/SubmittedDate/LastUpdatedDate）
        """
        try:
            search = arxiv.Search(
                query=query,
                max_results=limit,
                sort_by=sort_by
            )

            results = []
            for result in self.client.results(search):
                paper = Paper(
                    paper_id=result.entry_id.split("/")[-1],
                    title=result.title,
                    authors=[author.name for author in result.authors],
                    abstract=result.summary,
                    url=result.entry_id,
                    year=result.published.year if result.published else None,
                    source="arxiv"
                )
                results.append(paper)

            return results

        except Exception as e:
            print(f"arXiv搜索出错: {e}")
            return []

    def get_paper(self, arxiv_id: str) -> Optional[Paper]:
        """
        获取单篇论文详情

        Args:
            arxiv_id: arXiv ID（如 "2301.00001"）
        """
        try:
            search = arxiv.Search(id_list=[arxiv_id])
            results = list(self.client.results(search))

            if not results:
                return None

            result = results[0]
            return Paper(
                paper_id=result.entry_id.split("/")[-1],
                title=result.title,
                authors=[author.name for author in result.authors],
                abstract=result.summary,
                url=result.entry_id,
                year=result.published.year if result.published else None,
                source="arxiv"
            )
        except Exception as e:
            print(f"获取论文出错: {e}")
            return None

    def search_by_category(
        self,
        category: str,
        limit: int = 10
    ) -> List[Paper]:
        """
        按分类搜索（如 cs.AI, cs.CL, cs.LG）

        Args:
            category: arXiv分类（如 "cs.AI"）
            limit: 返回数量
        """
        return self.search(f"cat:{category}", limit, arxiv.SortCriterion.SubmittedDate)


# 测试代码
if __name__ == "__main__":
    searcher = ArxivSearch()

    print("=" * 50)
    print("arXiv 搜索测试")
    print("=" * 50)

    # 测试关键词搜索
    papers = searcher.search("transformer attention mechanism", limit=3)

    print(f"\n找到 {len(papers)} 篇论文:\n")
    for i, paper in enumerate(papers, 1):
        print(f"[{i}] {paper.title}")
        print(f"    作者: {', '.join(paper.authors[:3])}")
        print(f"    年份: {paper.year}")
        print(f"    链接: {paper.url}")
        print()

    # 测试分类搜索
    print("\n" + "=" * 50)
    print("cs.AI 最新论文:")
    print("=" * 50)

    ai_papers = searcher.search_by_category("cs.AI", limit=3)
    for i, paper in enumerate(ai_papers, 1):
        print(f"[{i}] {paper.title[:60]}...")
        print(f"    年份: {paper.year}")
        print()
