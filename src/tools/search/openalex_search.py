"""OpenAlex 论文搜索

OpenAlex 是一个开放的学术论文数据库，完全免费，无需API Key。
API 文档: https://docs.openalex.org/

优势:
- 免费、无需认证
- 2.5亿+论文
- 宽松的速率限制 (10 req/sec, 使用邮箱可更高)
"""
import httpx
from typing import List, Optional

from .semantic_scholar import Paper  # 复用Paper数据结构


class OpenAlexSearch:
    """OpenAlex 论文搜索"""

    BASE_URL = "https://api.openalex.org/works"

    def __init__(self, email: Optional[str] = None):
        """
        初始化 OpenAlex 搜索

        Args:
            email: 可选，提供邮箱可获得更高的速率限制（polite pool）
        """
        self.email = email
        self.headers = {"Accept": "application/json"}
        if email:
            self.headers["User-Agent"] = f"mailto:{email}"

    def search(self, query: str, limit: int = 10) -> List[Paper]:
        """
        搜索论文

        Args:
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            论文列表
        """
        params = {
            "search": query,
            "per-page": min(limit, 50),  # OpenAlex 最大50
            "sort": "cited_by_count:desc",  # 按引用数排序
        }

        # 添加邮箱到参数（polite pool）
        if self.email:
            params["mailto"] = self.email

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    self.BASE_URL,
                    params=params,
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            print(f"[OpenAlex] 搜索出错: {e}")
            return []

        papers = []
        for item in data.get("results", []):
            paper = self._parse_paper(item)
            if paper:
                papers.append(paper)

        return papers

    def _parse_paper(self, item: dict) -> Optional[Paper]:
        """解析 OpenAlex 论文数据为 Paper 对象"""
        try:
            # 提取作者
            authors = []
            for authorship in item.get("authorships", []):
                author = authorship.get("author", {})
                name = author.get("display_name", "")
                if name:
                    authors.append(name)

            # 提取年份
            year = item.get("publication_year")

            # 提取摘要（OpenAlex的摘要是倒排索引格式，需要重建）
            abstract = self._reconstruct_abstract(item.get("abstract_inverted_index"))

            # 提取URL（优先使用DOI）
            url = item.get("doi") or item.get("id", "")
            if url and url.startswith("https://doi.org/"):
                pass  # 已经是完整URL
            elif url and not url.startswith("http"):
                url = f"https://doi.org/{url}" if "/" in url else ""

            # 提取 paper_id（从 OpenAlex ID）
            paper_id = item.get("id", "").replace("https://openalex.org/", "")

            return Paper(
                paper_id=paper_id,
                title=item.get("title", "无标题"),
                authors=authors[:10],  # 限制作者数量
                abstract=abstract or "无摘要",
                url=url,
                year=year,
                source="openalex",
                citation_count=item.get("cited_by_count", 0),
            )
        except Exception as e:
            print(f"[OpenAlex] 解析论文失败: {e}")
            return None

    def _reconstruct_abstract(self, inverted_index: Optional[dict]) -> str:
        """
        从倒排索引重建摘要文本

        OpenAlex 的摘要以倒排索引格式存储:
        {"word1": [0, 5], "word2": [1, 3], ...}
        表示 word1 出现在位置0和5，word2出现在位置1和3
        """
        if not inverted_index:
            return ""

        # 重建词序列
        words = []
        for word, positions in inverted_index.items():
            for pos in positions:
                words.append((pos, word))

        # 按位置排序
        words.sort(key=lambda x: x[0])

        # 拼接成文本
        return " ".join(word for _, word in words)


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("OpenAlex 搜索测试")
    print("=" * 60)

    searcher = OpenAlexSearch()

    results = searcher.search("transformer attention mechanism", limit=5)

    print(f"\n找到 {len(results)} 篇论文:\n")

    for i, paper in enumerate(results, 1):
        print(f"[{i}] {paper.title}")
        print(f"    作者: {', '.join(paper.authors[:3])}")
        print(f"    年份: {paper.year}")
        print(f"    引用: {paper.citation_count}")
        print(f"    来源: {paper.source}")
        print()
