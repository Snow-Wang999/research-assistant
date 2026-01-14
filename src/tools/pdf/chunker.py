"""文档切片器

将解析后的 PDF 文档切分为适合 LLM 处理的文本块。
保留位置信息用于后续的句级追溯。
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from .pdf_parser import ParsedDocument, TextBlock, LayoutType


@dataclass
class TextChunk:
    """文本切片"""
    text: str
    chunk_id: int
    source_blocks: list[TextBlock] = field(default_factory=list)
    token_count: int = 0

    @property
    def pages(self) -> list[int]:
        """涉及的页码"""
        return sorted(set(b.page for b in self.source_blocks))

    @property
    def position_tags(self) -> list[str]:
        """位置标签列表"""
        return [b.position_tag for b in self.source_blocks]

    def get_text_with_positions(self) -> str:
        """获取带位置标签的文本"""
        # 简化版：整个 chunk 使用第一个块的位置
        if self.source_blocks:
            return self.text + self.source_blocks[0].position_tag
        return self.text


@dataclass
class ChunkedDocument:
    """切片后的文档"""
    file_path: str
    total_pages: int
    chunks: list[TextChunk] = field(default_factory=list)
    title: str = ""
    authors: str = ""
    abstract: str = ""

    def get_all_text(self) -> str:
        """获取所有切片的文本"""
        return "\n\n".join(chunk.text for chunk in self.chunks)

    def get_chunk_by_page(self, page: int) -> list[TextChunk]:
        """获取指定页的切片"""
        return [c for c in self.chunks if page in c.pages]


class TextChunker:
    """文本切片器"""

    # 句子结束符
    SENTENCE_ENDINGS = r'[.!?。！？]'

    # 段落分隔符
    PARAGRAPH_DELIMITERS = ["\n\n", "\n"]

    def __init__(
        self,
        chunk_size: int = 512,
        overlap_size: int = 50,
        min_chunk_size: int = 100
    ):
        """
        初始化切片器

        Args:
            chunk_size: 目标切片大小（token 数）
            overlap_size: 切片重叠大小（token 数）
            min_chunk_size: 最小切片大小
        """
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.min_chunk_size = min_chunk_size

    def _estimate_tokens(self, text: str) -> int:
        """
        估算 token 数量

        简单估算：英文约 4 字符/token，中文约 2 字符/token
        """
        # 统计中英文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars

        return chinese_chars // 2 + other_chars // 4

    def _split_into_sentences(self, text: str) -> list[str]:
        """将文本分割成句子"""
        # 使用正则分割，保留分隔符
        parts = re.split(f'({self.SENTENCE_ENDINGS})', text)

        sentences = []
        current = ""
        for part in parts:
            current += part
            if re.match(self.SENTENCE_ENDINGS, part):
                if current.strip():
                    sentences.append(current.strip())
                current = ""

        if current.strip():
            sentences.append(current.strip())

        return sentences

    def chunk(self, document: ParsedDocument) -> ChunkedDocument:
        """
        对解析后的文档进行切片

        Args:
            document: 解析后的 PDF 文档

        Returns:
            ChunkedDocument: 切片后的文档
        """
        chunks: list[TextChunk] = []
        chunk_id = 0

        # 按块处理
        current_text = ""
        current_blocks: list[TextBlock] = []
        current_tokens = 0

        for block in document.blocks:
            # 跳过图表
            if block.layout_type in [LayoutType.FIGURE, LayoutType.TABLE]:
                continue

            block_text = block.text.strip()
            if not block_text:
                continue

            block_tokens = self._estimate_tokens(block_text)

            # 如果当前块本身就超过 chunk_size，需要进一步切分
            if block_tokens > self.chunk_size:
                # 先保存当前累积的内容
                if current_text:
                    chunks.append(TextChunk(
                        text=current_text.strip(),
                        chunk_id=chunk_id,
                        source_blocks=current_blocks.copy(),
                        token_count=current_tokens
                    ))
                    chunk_id += 1
                    current_text = ""
                    current_blocks = []
                    current_tokens = 0

                # 切分大块
                sub_chunks = self._split_large_block(block)
                for sub_chunk in sub_chunks:
                    chunks.append(TextChunk(
                        text=sub_chunk,
                        chunk_id=chunk_id,
                        source_blocks=[block],
                        token_count=self._estimate_tokens(sub_chunk)
                    ))
                    chunk_id += 1
                continue

            # 判断是否需要开始新的 chunk
            if current_tokens + block_tokens > self.chunk_size:
                if current_text:
                    chunks.append(TextChunk(
                        text=current_text.strip(),
                        chunk_id=chunk_id,
                        source_blocks=current_blocks.copy(),
                        token_count=current_tokens
                    ))
                    chunk_id += 1

                    # 重叠处理：保留最后一个块
                    if self.overlap_size > 0 and current_blocks:
                        last_block = current_blocks[-1]
                        last_tokens = self._estimate_tokens(last_block.text)
                        if last_tokens <= self.overlap_size:
                            current_text = last_block.text + "\n\n"
                            current_blocks = [last_block]
                            current_tokens = last_tokens
                        else:
                            current_text = ""
                            current_blocks = []
                            current_tokens = 0
                    else:
                        current_text = ""
                        current_blocks = []
                        current_tokens = 0

            # 添加标题标记
            if block.layout_type == LayoutType.TITLE:
                current_text += f"\n\n## {block_text}\n\n"
            else:
                current_text += block_text + "\n\n"

            current_blocks.append(block)
            current_tokens += block_tokens

        # 保存最后一个 chunk
        if current_text.strip():
            chunks.append(TextChunk(
                text=current_text.strip(),
                chunk_id=chunk_id,
                source_blocks=current_blocks,
                token_count=current_tokens
            ))

        # 过滤太小的 chunk（除了最后一个）
        if len(chunks) > 1:
            chunks = [
                c for i, c in enumerate(chunks)
                if c.token_count >= self.min_chunk_size or i == len(chunks) - 1
            ]
            # 重新编号
            for i, chunk in enumerate(chunks):
                chunk.chunk_id = i

        return ChunkedDocument(
            file_path=document.file_path,
            total_pages=document.total_pages,
            chunks=chunks,
            title=document.title,
            authors=document.authors,
            abstract=document.abstract
        )

    def _split_large_block(self, block: TextBlock) -> list[str]:
        """切分超大文本块"""
        text = block.text
        sentences = self._split_into_sentences(text)

        chunks = []
        current_chunk = ""
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)

            if current_tokens + sentence_tokens > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
                current_tokens = sentence_tokens
            else:
                current_chunk += sentence + " "
                current_tokens += sentence_tokens

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks


# 便捷函数
def chunk_pdf(
    pdf_path: str,
    chunk_size: int = 512,
    overlap_size: int = 50
) -> ChunkedDocument:
    """
    解析并切片 PDF 文档

    Args:
        pdf_path: PDF 文件路径
        chunk_size: 切片大小
        overlap_size: 重叠大小

    Returns:
        ChunkedDocument: 切片后的文档
    """
    from .pdf_parser import PDFParser

    parser = PDFParser()
    chunker = TextChunker(chunk_size=chunk_size, overlap_size=overlap_size)

    parsed = parser.parse(pdf_path)
    return chunker.chunk(parsed)


# 测试代码
if __name__ == "__main__":
    import sys

    # 测试切片
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "./data/pdf_cache/1706.03762.pdf"

    print("=" * 60)
    print(f"切片测试: {pdf_path}")
    print("=" * 60)

    try:
        result = chunk_pdf(pdf_path, chunk_size=512)

        print(f"\n总页数: {result.total_pages}")
        print(f"切片数: {len(result.chunks)}")

        if result.title:
            print(f"\n标题: {result.title[:80]}...")

        # 显示切片统计
        print("\n" + "-" * 40)
        print("切片统计:")
        print("-" * 40)
        for i, chunk in enumerate(result.chunks[:5]):
            print(f"\n[Chunk {chunk.chunk_id}]")
            print(f"  Token 数: {chunk.token_count}")
            print(f"  页码: {chunk.pages}")
            print(f"  内容预览: {chunk.text[:100]}...")

        # 总 token 统计
        total_tokens = sum(c.token_count for c in result.chunks)
        avg_tokens = total_tokens / len(result.chunks) if result.chunks else 0
        print(f"\n总 Token 数: {total_tokens}")
        print(f"平均每片: {avg_tokens:.0f} tokens")

    except FileNotFoundError as e:
        print(f"错误: {e}")
        print("请先下载测试 PDF 文件")
