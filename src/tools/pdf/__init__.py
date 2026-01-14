"""PDF 处理模块

v0.4.0 新增功能：
- arXiv PDF 下载
- PDF 解析（PyMuPDF）
- 文档切片（带位置信息）
- 论文处理器（集成流程）
"""

from .arxiv_downloader import ArxivDownloader
from .pdf_parser import PDFParser, ParsedDocument, TextBlock, LayoutType
from .chunker import TextChunker, ChunkedDocument, TextChunk, chunk_pdf
from .paper_processor import PaperProcessor, ProcessedPaper, get_paper_full_text, get_paper_chunks

__all__ = [
    # 下载器
    "ArxivDownloader",
    # 解析器
    "PDFParser",
    "ParsedDocument",
    "TextBlock",
    "LayoutType",
    # 切片器
    "TextChunker",
    "ChunkedDocument",
    "TextChunk",
    "chunk_pdf",
    # 论文处理器
    "PaperProcessor",
    "ProcessedPaper",
    "get_paper_full_text",
    "get_paper_chunks",
]
