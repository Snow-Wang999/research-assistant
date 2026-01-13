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
        # 搜索更多结果，然后在本地过滤和排序
        params = {
            "search": query,
            "per-page": min(limit * 3, 50),  # 多搜一些以便过滤
            # 默认按相关性排序（relevance_score），不指定sort
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

        # 综合排序：相关性 + 时间 + 引用数
        import math
        from datetime import datetime
        current_year = datetime.now().year

        def composite_score(paper, idx):
            # 1. 相关性分数（OpenAlex 返回顺序）
            relevance = max(0, 30 - idx)  # 前30名有相关性加分

            # 2. 时间分数（越新越高）
            year = paper.year if paper.year else 2000
            years_ago = current_year - year
            # 近5年的论文获得时间加分：2024=25分, 2023=20分, 2022=15分...
            recency = max(0, (5 - years_ago) * 5)

            # 3. 引用分数（取对数避免高引用完全主导）
            citations = math.log10(paper.citation_count + 1) * 3 if paper.citation_count else 0

            # 综合得分：时间权重最高，其次相关性，最后引用
            return recency + relevance + citations

        # 排序
        scored_papers = [(p, composite_score(p, i)) for i, p in enumerate(papers)]
        scored_papers.sort(key=lambda x: x[1], reverse=True)

        return [p for p, _ in scored_papers[:limit]]

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
