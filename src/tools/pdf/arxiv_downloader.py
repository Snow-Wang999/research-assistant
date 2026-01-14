"""arXiv PDF 下载器

从 arXiv 下载论文 PDF 文件。
"""

import os
import re
import httpx
import asyncio
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class DownloadResult:
    """下载结果"""
    arxiv_id: str
    success: bool
    file_path: Optional[str] = None
    error: Optional[str] = None


class ArxivDownloader:
    """arXiv PDF 下载器"""

    # arXiv PDF 下载链接模板
    PDF_URL_TEMPLATE = "https://arxiv.org/pdf/{arxiv_id}.pdf"

    def __init__(self, cache_dir: str = "./data/pdf_cache"):
        """
        初始化下载器

        Args:
            cache_dir: PDF 缓存目录
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _normalize_arxiv_id(self, arxiv_id: str) -> str:
        """
        标准化 arXiv ID

        支持格式：
        - 2301.00001
        - arxiv:2301.00001
        - https://arxiv.org/abs/2301.00001
        - https://arxiv.org/pdf/2301.00001.pdf
        """
        # 移除常见前缀
        arxiv_id = arxiv_id.strip()

        # 从 URL 中提取 ID
        url_patterns = [
            r"arxiv\.org/abs/([0-9]+\.[0-9]+)",
            r"arxiv\.org/pdf/([0-9]+\.[0-9]+)",
            r"arxiv:([0-9]+\.[0-9]+)",
        ]
        for pattern in url_patterns:
            match = re.search(pattern, arxiv_id)
            if match:
                return match.group(1)

        # 直接匹配 ID 格式
        id_match = re.search(r"([0-9]{4}\.[0-9]{4,5})(v[0-9]+)?", arxiv_id)
        if id_match:
            return id_match.group(1)

        return arxiv_id

    def _get_cache_path(self, arxiv_id: str) -> Path:
        """获取 PDF 缓存路径"""
        safe_id = arxiv_id.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_id}.pdf"

    def is_cached(self, arxiv_id: str) -> bool:
        """检查 PDF 是否已缓存"""
        arxiv_id = self._normalize_arxiv_id(arxiv_id)
        cache_path = self._get_cache_path(arxiv_id)
        return cache_path.exists() and cache_path.stat().st_size > 0

    def get_cached_path(self, arxiv_id: str) -> Optional[str]:
        """获取缓存的 PDF 路径（如果存在）"""
        arxiv_id = self._normalize_arxiv_id(arxiv_id)
        if self.is_cached(arxiv_id):
            return str(self._get_cache_path(arxiv_id))
        return None

    async def download_async(self, arxiv_id: str, force: bool = False) -> DownloadResult:
        """
        异步下载 arXiv PDF

        Args:
            arxiv_id: arXiv 论文 ID
            force: 是否强制重新下载（忽略缓存）

        Returns:
            DownloadResult: 下载结果
        """
        arxiv_id = self._normalize_arxiv_id(arxiv_id)
        cache_path = self._get_cache_path(arxiv_id)

        # 检查缓存
        if not force and self.is_cached(arxiv_id):
            return DownloadResult(
                arxiv_id=arxiv_id,
                success=True,
                file_path=str(cache_path)
            )

        # 构建下载 URL
        pdf_url = self.PDF_URL_TEMPLATE.format(arxiv_id=arxiv_id)

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(pdf_url)
                response.raise_for_status()

                # 验证是 PDF 文件
                content_type = response.headers.get("content-type", "")
                if "pdf" not in content_type.lower() and not response.content[:4] == b"%PDF":
                    return DownloadResult(
                        arxiv_id=arxiv_id,
                        success=False,
                        error=f"返回的不是 PDF 文件: {content_type}"
                    )

                # 保存文件
                cache_path.write_bytes(response.content)

                return DownloadResult(
                    arxiv_id=arxiv_id,
                    success=True,
                    file_path=str(cache_path)
                )

        except httpx.HTTPStatusError as e:
            return DownloadResult(
                arxiv_id=arxiv_id,
                success=False,
                error=f"HTTP 错误 {e.response.status_code}: {str(e)}"
            )
        except Exception as e:
            return DownloadResult(
                arxiv_id=arxiv_id,
                success=False,
                error=f"下载失败: {str(e)}"
            )

    def download(self, arxiv_id: str, force: bool = False) -> DownloadResult:
        """
        同步下载 arXiv PDF（封装异步方法）

        Args:
            arxiv_id: arXiv 论文 ID
            force: 是否强制重新下载

        Returns:
            DownloadResult: 下载结果
        """
        return asyncio.run(self.download_async(arxiv_id, force))

    async def download_batch_async(
        self,
        arxiv_ids: list[str],
        force: bool = False,
        max_concurrent: int = 5
    ) -> list[DownloadResult]:
        """
        批量异步下载 arXiv PDF

        Args:
            arxiv_ids: arXiv 论文 ID 列表
            force: 是否强制重新下载
            max_concurrent: 最大并发数

        Returns:
            list[DownloadResult]: 下载结果列表
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def download_with_limit(arxiv_id: str) -> DownloadResult:
            async with semaphore:
                return await self.download_async(arxiv_id, force)

        tasks = [download_with_limit(aid) for aid in arxiv_ids]
        return await asyncio.gather(*tasks)

    def download_batch(
        self,
        arxiv_ids: list[str],
        force: bool = False,
        max_concurrent: int = 5
    ) -> list[DownloadResult]:
        """
        批量同步下载 arXiv PDF
        """
        return asyncio.run(self.download_batch_async(arxiv_ids, force, max_concurrent))

    def clear_cache(self, arxiv_id: Optional[str] = None) -> int:
        """
        清理缓存

        Args:
            arxiv_id: 指定清理某个 ID 的缓存，为 None 时清理全部

        Returns:
            int: 清理的文件数量
        """
        if arxiv_id:
            arxiv_id = self._normalize_arxiv_id(arxiv_id)
            cache_path = self._get_cache_path(arxiv_id)
            if cache_path.exists():
                cache_path.unlink()
                return 1
            return 0

        # 清理全部
        count = 0
        for pdf_file in self.cache_dir.glob("*.pdf"):
            pdf_file.unlink()
            count += 1
        return count


# 测试代码
if __name__ == "__main__":
    import sys

    downloader = ArxivDownloader()

    # 测试 ID 标准化
    test_ids = [
        "2301.00001",
        "arxiv:2301.00001",
        "https://arxiv.org/abs/2301.00001",
        "https://arxiv.org/pdf/2301.00001.pdf",
    ]

    print("=" * 50)
    print("ID 标准化测试")
    print("=" * 50)
    for tid in test_ids:
        normalized = downloader._normalize_arxiv_id(tid)
        print(f"{tid} -> {normalized}")

    # 测试下载
    print("\n" + "=" * 50)
    print("PDF 下载测试")
    print("=" * 50)

    # 使用一篇知名论文测试 (Attention Is All You Need)
    test_arxiv_id = "1706.03762"
    print(f"\n下载论文: {test_arxiv_id}")

    result = downloader.download(test_arxiv_id)

    if result.success:
        print(f"下载成功!")
        print(f"文件路径: {result.file_path}")
        print(f"文件大小: {os.path.getsize(result.file_path) / 1024:.1f} KB")
    else:
        print(f"下载失败: {result.error}")
