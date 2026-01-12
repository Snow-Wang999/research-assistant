"""Semantic Scholar 论文搜索"""
import httpx
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
    source: str = "semantic_scholar"


class SemanticScholarSearch:
    """Semantic Scholar 论文搜索工具"""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.headers = {"x-api-key": api_key} if api_key else {}

    def search(
        self,
        query: str,
        limit: int = 10,
        fields: str = "title,abstract,url,year,authors,citationCount"
    ) -> List[Paper]:
        """搜索论文"""
        try:
            response = httpx.get(
                f"{self.BASE_URL}/paper/search",
                params={"query": query, "limit": limit, "fields": fields},
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()

            data = response.json().get("data", [])

            results = []
            for item in data:
                paper = Paper(
                    paper_id=item.get("paperId", ""),
                    title=item.get("title", ""),
                    authors=[a.get("name", "") for a in item.get("authors", [])],
                    abstract=item.get("abstract", "") or "",
                    url=item.get("url", "") or f"https://semanticscholar.org/paper/{item.get('paperId', '')}",
                    year=item.get("year"),
                    citation_count=item.get("citationCount"),
                    source="semantic_scholar"
                )
                results.append(paper)

            return results

        except Exception as e:
            print(f"搜索出错: {e}")
            return []

    def get_paper(self, paper_id: str) -> Optional[Paper]:
        """获取单篇论文详情"""
        try:
            response = httpx.get(
                f"{self.BASE_URL}/paper/{paper_id}",
                params={"fields": "title,abstract,url,year,authors,citationCount"},
                headers=self.headers,
                timeout=30.0
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()

            item = response.json()
            return Paper(
                paper_id=item.get("paperId", ""),
                title=item.get("title", ""),
                authors=[a.get("name", "") for a in item.get("authors", [])],
                abstract=item.get("abstract", "") or "",
                url=item.get("url", "") or f"https://semanticscholar.org/paper/{item.get('paperId', '')}",
                year=item.get("year"),
                citation_count=item.get("citationCount"),
                source="semantic_scholar"
            )
        except Exception as e:
            print(f"获取论文出错: {e}")
            return None


# 测试代码
if __name__ == "__main__":
    searcher = SemanticScholarSearch()
    papers = searcher.search("transformer attention mechanism", limit=3)

    print(f"\n找到 {len(papers)} 篇论文:\n")
    for i, paper in enumerate(papers, 1):
        print(f"[{i}] {paper.title}")
        print(f"    作者: {', '.join(paper.authors[:3])}")
        print(f"    年份: {paper.year}")
        print(f"    引用: {paper.citation_count}")
        print()
