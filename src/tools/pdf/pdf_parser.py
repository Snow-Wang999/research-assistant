"""PDF 解析器

使用 PyMuPDF (fitz) 解析 PDF 文档，提取文本和位置信息。
支持双栏论文布局。
"""

import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class LayoutType(Enum):
    """布局类型"""
    TEXT = "text"
    TITLE = "title"
    FIGURE = "figure"
    TABLE = "table"


@dataclass
class TextBlock:
    """文本块"""
    text: str
    page: int
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1)
    layout_type: LayoutType = LayoutType.TEXT
    font_size: float = 0.0
    is_bold: bool = False

    @property
    def x0(self) -> float:
        return self.bbox[0]

    @property
    def y0(self) -> float:
        return self.bbox[1]

    @property
    def x1(self) -> float:
        return self.bbox[2]

    @property
    def y1(self) -> float:
        return self.bbox[3]

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def position_tag(self) -> str:
        """位置标签（用于后续追溯）"""
        return f"@@{self.page}\t{self.x0:.1f}\t{self.x1:.1f}\t{self.y0:.1f}\t{self.y1:.1f}##"


@dataclass
class ParsedDocument:
    """解析后的文档"""
    file_path: str
    total_pages: int
    blocks: list[TextBlock] = field(default_factory=list)
    title: str = ""
    authors: str = ""
    abstract: str = ""

    def get_full_text(self) -> str:
        """获取全文（仅 text 类型的块）"""
        return "\n\n".join(
            block.text for block in self.blocks
            if block.layout_type in [LayoutType.TEXT, LayoutType.TITLE]
        )

    def get_text_with_positions(self) -> str:
        """获取带位置标签的全文"""
        return "\n\n".join(
            block.text + block.position_tag
            for block in self.blocks
            if block.layout_type in [LayoutType.TEXT, LayoutType.TITLE]
        )


class PDFParser:
    """PDF 解析器（基于 PyMuPDF）"""

    # 标题检测的字体大小阈值（相对于正文平均字体）
    TITLE_FONT_RATIO = 1.2

    # 双栏检测阈值
    TWO_COLUMN_RATIO = 0.4  # 如果大部分块宽度小于页面宽度的这个比例，认为是双栏

    def __init__(self):
        """初始化解析器"""
        try:
            import fitz
            self.fitz = fitz
        except ImportError:
            raise ImportError(
                "PyMuPDF 未安装，请运行: pip install pymupdf"
            )

    def parse(self, pdf_path: str) -> ParsedDocument:
        """
        解析 PDF 文档

        Args:
            pdf_path: PDF 文件路径

        Returns:
            ParsedDocument: 解析结果
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        doc = self.fitz.open(str(pdf_path))
        all_blocks: list[TextBlock] = []

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_blocks = self._extract_page_blocks(page, page_num + 1)
                all_blocks.extend(page_blocks)

            # 检测并处理双栏布局
            if self._is_two_column(all_blocks, doc[0].rect.width if doc else 612):
                all_blocks = self._sort_two_column(all_blocks, doc[0].rect.width)

            # 分类布局类型
            all_blocks = self._classify_blocks(all_blocks)

            # 合并相邻的同类型块
            all_blocks = self._merge_adjacent_blocks(all_blocks)

            # 提取元数据
            title, authors, abstract = self._extract_metadata(all_blocks)

            return ParsedDocument(
                file_path=str(pdf_path),
                total_pages=len(doc),
                blocks=all_blocks,
                title=title,
                authors=authors,
                abstract=abstract
            )
        finally:
            doc.close()

    def _extract_page_blocks(self, page, page_num: int) -> list[TextBlock]:
        """提取页面中的文本块"""
        blocks = []
        page_dict = page.get_text("dict")

        for block in page_dict.get("blocks", []):
            # 跳过图片块
            if block.get("type") == 1:  # image block
                blocks.append(TextBlock(
                    text="[FIGURE]",
                    page=page_num,
                    bbox=tuple(block["bbox"]),
                    layout_type=LayoutType.FIGURE
                ))
                continue

            # 处理文本块
            if block.get("type") == 0:  # text block
                text_parts = []
                font_sizes = []
                is_bold = False

                for line in block.get("lines", []):
                    line_text = ""
                    for span in line.get("spans", []):
                        span_text = span.get("text", "")
                        line_text += span_text
                        font_sizes.append(span.get("size", 10))
                        # 检测粗体
                        if "bold" in span.get("font", "").lower():
                            is_bold = True
                    text_parts.append(line_text)

                text = " ".join(text_parts).strip()
                if not text:
                    continue

                avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 10

                blocks.append(TextBlock(
                    text=text,
                    page=page_num,
                    bbox=tuple(block["bbox"]),
                    font_size=avg_font_size,
                    is_bold=is_bold
                ))

        return blocks

    def _is_two_column(self, blocks: list[TextBlock], page_width: float) -> bool:
        """检测是否为双栏布局"""
        if not blocks:
            return False

        # 计算每个块的宽度占比
        narrow_blocks = sum(
            1 for b in blocks
            if b.width < page_width * self.TWO_COLUMN_RATIO
            and b.layout_type != LayoutType.FIGURE
        )

        return narrow_blocks / len(blocks) > 0.5

    def _sort_two_column(self, blocks: list[TextBlock], page_width: float) -> list[TextBlock]:
        """对双栏布局的块进行排序"""
        mid = page_width / 2

        # 按页分组
        pages = {}
        for block in blocks:
            if block.page not in pages:
                pages[block.page] = []
            pages[block.page].append(block)

        sorted_blocks = []
        for page_num in sorted(pages.keys()):
            page_blocks = pages[page_num]

            # 分成左右两栏
            left_col = [b for b in page_blocks if b.x0 + b.width / 2 < mid]
            right_col = [b for b in page_blocks if b.x0 + b.width / 2 >= mid]

            # 跨栏的块（宽度超过一半）放在正确位置
            full_width = [b for b in page_blocks if b.width > page_width * 0.6]

            # 按 y 坐标排序
            left_col = sorted(left_col, key=lambda b: b.y0)
            right_col = sorted(right_col, key=lambda b: b.y0)

            # 合并：先左栏，后右栏（简化处理）
            # 更精确的处理应该交替插入
            combined = []
            for block in full_width:
                if block in left_col:
                    left_col.remove(block)
                if block in right_col:
                    right_col.remove(block)

            # 交替合并左右栏（基于 y 位置）
            l_idx, r_idx = 0, 0
            while l_idx < len(left_col) or r_idx < len(right_col):
                # 处理跨栏块
                for fw in full_width:
                    if l_idx < len(left_col) and fw.y0 <= left_col[l_idx].y0:
                        combined.append(fw)
                        full_width.remove(fw)

                if l_idx < len(left_col):
                    combined.append(left_col[l_idx])
                    l_idx += 1

                if l_idx >= len(left_col) and r_idx < len(right_col):
                    combined.append(right_col[r_idx])
                    r_idx += 1
                elif r_idx < len(right_col) and (
                    l_idx >= len(left_col) or
                    right_col[r_idx].y0 < left_col[l_idx].y0 - 50
                ):
                    combined.append(right_col[r_idx])
                    r_idx += 1

            # 添加剩余的跨栏块
            combined.extend(full_width)

            sorted_blocks.extend(combined)

        return sorted_blocks

    def _classify_blocks(self, blocks: list[TextBlock]) -> list[TextBlock]:
        """分类文本块的布局类型"""
        if not blocks:
            return blocks

        # 计算平均字体大小（排除已标记的图表）
        text_blocks = [b for b in blocks if b.layout_type != LayoutType.FIGURE]
        if not text_blocks:
            return blocks

        avg_font = sum(b.font_size for b in text_blocks) / len(text_blocks)

        for block in blocks:
            if block.layout_type == LayoutType.FIGURE:
                continue

            # 标题检测
            is_title = (
                block.font_size > avg_font * self.TITLE_FONT_RATIO or
                block.is_bold and len(block.text) < 200
            )

            # 章节标题模式
            section_patterns = [
                r"^[0-9]+\.?\s+[A-Z]",  # 1. Introduction, 2 Methods
                r"^[IVX]+\.?\s+",  # I. II. III.
                r"^(Abstract|Introduction|Related Work|Method|Experiment|Conclusion|Reference)",
                r"^(摘要|引言|相关工作|方法|实验|结论|参考文献)",
            ]

            is_section_title = any(
                re.match(p, block.text.strip(), re.IGNORECASE)
                for p in section_patterns
            )

            if is_title or is_section_title:
                block.layout_type = LayoutType.TITLE

        return blocks

    def _merge_adjacent_blocks(self, blocks: list[TextBlock]) -> list[TextBlock]:
        """合并相邻的同类型文本块"""
        if not blocks:
            return blocks

        merged = []
        current = None

        for block in blocks:
            if current is None:
                current = block
                continue

            # 判断是否应该合并
            should_merge = (
                current.page == block.page and
                current.layout_type == block.layout_type == LayoutType.TEXT and
                abs(block.y0 - current.y1) < 20 and  # 垂直距离小
                abs(current.x0 - block.x0) < 50  # 左对齐相近
            )

            if should_merge:
                # 合并文本
                current = TextBlock(
                    text=current.text + " " + block.text,
                    page=current.page,
                    bbox=(
                        min(current.x0, block.x0),
                        current.y0,
                        max(current.x1, block.x1),
                        block.y1
                    ),
                    layout_type=current.layout_type,
                    font_size=current.font_size
                )
            else:
                merged.append(current)
                current = block

        if current:
            merged.append(current)

        return merged

    def _extract_metadata(self, blocks: list[TextBlock]) -> tuple[str, str, str]:
        """提取论文元数据（标题、作者、摘要）"""
        title = ""
        authors = ""
        abstract = ""

        if not blocks:
            return title, authors, abstract

        # 第一页的块
        first_page_blocks = [b for b in blocks if b.page == 1]

        # 标题：第一页最大字体的块
        title_candidates = [
            b for b in first_page_blocks[:10]
            if b.layout_type == LayoutType.TITLE and len(b.text) < 300
        ]
        if title_candidates:
            title = max(title_candidates, key=lambda b: b.font_size).text

        # 摘要：查找 "Abstract" 后的内容
        for i, block in enumerate(first_page_blocks):
            text_lower = block.text.lower().strip()
            if text_lower.startswith("abstract"):
                # 摘要可能在同一块或下一块
                if len(block.text) > 50:
                    abstract = block.text
                elif i + 1 < len(first_page_blocks):
                    abstract = first_page_blocks[i + 1].text
                break

        return title, authors, abstract


# 测试代码
if __name__ == "__main__":
    import sys

    parser = PDFParser()

    # 测试解析
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # 默认测试文件
        pdf_path = "./data/pdf_cache/1706.03762.pdf"

    print("=" * 60)
    print(f"解析 PDF: {pdf_path}")
    print("=" * 60)

    try:
        result = parser.parse(pdf_path)

        print(f"\n总页数: {result.total_pages}")
        print(f"文本块数: {len(result.blocks)}")

        if result.title:
            print(f"\n标题: {result.title[:100]}...")

        if result.abstract:
            print(f"\n摘要: {result.abstract[:200]}...")

        # 显示前几个块
        print("\n" + "-" * 40)
        print("前 5 个文本块:")
        print("-" * 40)
        for i, block in enumerate(result.blocks[:5]):
            print(f"\n[{i+1}] 页{block.page} | {block.layout_type.value}")
            print(f"    位置: ({block.x0:.0f}, {block.y0:.0f}) - ({block.x1:.0f}, {block.y1:.0f})")
            print(f"    字体: {block.font_size:.1f}")
            print(f"    内容: {block.text[:80]}...")

    except FileNotFoundError as e:
        print(f"错误: {e}")
        print("请先下载测试 PDF 文件")
