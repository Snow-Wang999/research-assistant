"""论文处理器

集成 PDF 下载、解析、切片的完整流程。
供 Deep Research 模块使用。
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from .arxiv_downloader import ArxivDownloader, DownloadResult
from .pdf_parser import PDFParser, ParsedDocument
from .chunker import TextChunker, ChunkedDocument, TextChunk


@dataclass
class ProcessedPaper:
    """处理后的论文"""
    arxiv_id: str
    title: str
    abstract: str
    full_text: str  # 全文（用于 Deep Research）
    chunks: list[TextChunk]  # 切片（用于向量检索）
    total_pages: int
    pdf_path: Optional[str] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None

    def get_chunk_texts(self) -> list[str]:
        """获取所有切片的文本"""
        return [chunk.text for chunk in self.chunks]


class PaperProcessor:
    """论文处理器"""

    def __init__(
        self,
        cache_dir: str = "./data/pdf_cache",
        chunk_size: int = 512,
        overlap_size: int = 50
    ):
        """
        初始化处理器

        Args:
            cache_dir: PDF 缓存目录
            chunk_size: 切片大小
            overlap_size: 切片重叠
        """
        self.downloader = ArxivDownloader(cache_dir=cache_dir)
        self.parser = PDFParser()
        self.chunker = TextChunker(
            chunk_size=chunk_size,
            overlap_size=overlap_size
        )

    async def process_async(
        self,
        arxiv_id: str,
        force_download: bool = False
    ) -> ProcessedPaper:
        """
        异步处理单篇论文

        Args:
            arxiv_id: arXiv ID
            force_download: 强制重新下载

        Returns:
            ProcessedPaper: 处理结果
        """
        # 1. 下载 PDF
        download_result = await self.downloader.download_async(
            arxiv_id, force=force_download
        )

        if not download_result.success:
            return ProcessedPaper(
                arxiv_id=arxiv_id,
                title="",
                abstract="",
                full_text="",
                chunks=[],
                total_pages=0,
                error=f"下载失败: {download_result.error}"
            )

        # 2. 解析 PDF
        try:
            parsed = self.parser.parse(download_result.file_path)
        except Exception as e:
            return ProcessedPaper(
                arxiv_id=arxiv_id,
                title="",
                abstract="",
                full_text="",
                chunks=[],
                total_pages=0,
                pdf_path=download_result.file_path,
                error=f"解析失败: {str(e)}"
            )

        # 3. 切片
        try:
            chunked = self.chunker.chunk(parsed)
        except Exception as e:
            return ProcessedPaper(
                arxiv_id=arxiv_id,
                title=parsed.title,
                abstract=parsed.abstract,
                full_text=parsed.get_full_text(),
                chunks=[],
                total_pages=parsed.total_pages,
                pdf_path=download_result.file_path,
                error=f"切片失败: {str(e)}"
            )

        return ProcessedPaper(
            arxiv_id=arxiv_id,
            title=chunked.title,
            abstract=chunked.abstract,
            full_text=parsed.get_full_text(),
            chunks=chunked.chunks,
            total_pages=chunked.total_pages,
            pdf_path=download_result.file_path
        )

    def process(
        self,
        arxiv_id: str,
        force_download: bool = False
    ) -> ProcessedPaper:
        """同步处理单篇论文"""
        return asyncio.run(self.process_async(arxiv_id, force_download))

    async def process_batch_async(
        self,
        arxiv_ids: list[str],
        force_download: bool = False,
        max_concurrent: int = 3
    ) -> list[ProcessedPaper]:
        """
        批量异步处理论文

        Args:
            arxiv_ids: arXiv ID 列表
            force_download: 强制重新下载
            max_concurrent: 最大并发数

        Returns:
            list[ProcessedPaper]: 处理结果列表
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_limit(arxiv_id: str) -> ProcessedPaper:
            async with semaphore:
                return await self.process_async(arxiv_id, force_download)

        tasks = [process_with_limit(aid) for aid in arxiv_ids]
        return await asyncio.gather(*tasks)

    def process_batch(
        self,
        arxiv_ids: list[str],
        force_download: bool = False,
        max_concurrent: int = 3
    ) -> list[ProcessedPaper]:
        """批量同步处理论文"""
        return asyncio.run(
            self.process_batch_async(arxiv_ids, force_download, max_concurrent)
        )

    def is_cached(self, arxiv_id: str) -> bool:
        """检查论文是否已缓存"""
        return self.downloader.is_cached(arxiv_id)


# 便捷函数
def get_paper_full_text(arxiv_id: str) -> Optional[str]:
    """
    获取论文全文（简化接口）

    Args:
        arxiv_id: arXiv ID

    Returns:
        str: 论文全文，失败返回 None
    """
    processor = PaperProcessor()
    result = processor.process(arxiv_id)
    if result.success:
        return result.full_text
    return None


def get_paper_chunks(
    arxiv_id: str,
    chunk_size: int = 512
) -> list[str]:
    """
    获取论文切片（简化接口）

    Args:
        arxiv_id: arXiv ID
        chunk_size: 切片大小

    Returns:
        list[str]: 切片文本列表
    """
    processor = PaperProcessor(chunk_size=chunk_size)
    result = processor.process(arxiv_id)
    if result.success:
        return result.get_chunk_texts()
    return []


# 测试代码
if __name__ == "__main__":
    import time

    processor = PaperProcessor()

    print("=" * 60)
    print("论文处理器测试")
    print("=" * 60)

    # 测试单篇处理
    test_id = "1706.03762"
    print(f"\n处理论文: {test_id}")

    start = time.time()
    result = processor.process(test_id)
    elapsed = time.time() - start

    if result.success:
        print(f"\n处理成功! 耗时: {elapsed:.2f}s")
        print(f"  标题: {result.title[:50]}...")
        print(f"  页数: {result.total_pages}")
        print(f"  切片数: {len(result.chunks)}")
        print(f"  全文长度: {len(result.full_text)} 字符")
    else:
        print(f"\n处理失败: {result.error}")

    # 测试批量处理
    print("\n" + "=" * 60)
    print("批量处理测试")
    print("=" * 60)

    test_ids = ["2301.00001", "2301.00002"]  # 测试 ID
    print(f"\n处理 {len(test_ids)} 篇论文...")

    start = time.time()
    results = processor.process_batch(test_ids)
    elapsed = time.time() - start

    print(f"\n批量处理完成! 总耗时: {elapsed:.2f}s")
    for r in results:
        status = "成功" if r.success else f"失败: {r.error}"
        print(f"  {r.arxiv_id}: {status}")
