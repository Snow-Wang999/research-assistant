"""语义压缩器 - 解决Context爆炸问题"""
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class CompressedContent:
    """压缩后的内容"""
    original_length: int
    compressed_length: int
    content: str
    key_points: List[str]


class SemanticCompressor:
    """
    语义压缩器

    核心思想：使用LLM对搜索结果进行语义压缩，
    只保留与查询相关的关键信息，大幅减少Token消耗。

    这是V3架构的核心技术之一。
    """

    def __init__(self, llm_client=None):
        """
        初始化压缩器

        Args:
            llm_client: LLM客户端（用于语义压缩）
        """
        self.llm_client = llm_client

    def compress(
        self,
        content: str,
        query: str,
        max_length: int = 500
    ) -> CompressedContent:
        """
        压缩内容

        Args:
            content: 原始内容
            query: 用户查询（用于相关性判断）
            max_length: 压缩后最大长度

        Returns:
            CompressedContent: 压缩结果
        """
        original_length = len(content)

        # MVP阶段：使用简单截断 + 关键句提取
        # TODO: 后续替换为LLM语义压缩
        if self.llm_client is None:
            return self._simple_compress(content, query, max_length)

        return self._llm_compress(content, query, max_length)

    def _simple_compress(
        self,
        content: str,
        query: str,
        max_length: int
    ) -> CompressedContent:
        """简单压缩（不使用LLM）"""
        original_length = len(content)

        # 按句子分割
        sentences = self._split_sentences(content)

        # 简单相关性评分：包含查询词的句子得分更高
        query_words = set(query.lower().split())
        scored_sentences = []

        for sent in sentences:
            score = sum(1 for word in query_words if word in sent.lower())
            scored_sentences.append((score, sent))

        # 按得分排序，取最相关的句子
        scored_sentences.sort(key=lambda x: x[0], reverse=True)

        # 拼接直到达到长度限制
        compressed_parts = []
        current_length = 0
        key_points = []

        for score, sent in scored_sentences:
            if current_length + len(sent) > max_length:
                break
            compressed_parts.append(sent)
            current_length += len(sent)
            if score > 0:
                key_points.append(sent[:100])

        compressed_content = " ".join(compressed_parts)

        return CompressedContent(
            original_length=original_length,
            compressed_length=len(compressed_content),
            content=compressed_content,
            key_points=key_points[:5]
        )

    def _llm_compress(
        self,
        content: str,
        query: str,
        max_length: int
    ) -> CompressedContent:
        """使用LLM进行语义压缩"""
        # TODO: 实现LLM压缩
        # 提示词模板：
        # "请根据用户查询'{query}'，从以下内容中提取最相关的信息，
        #  压缩到{max_length}字以内，保留关键数据和结论。"
        raise NotImplementedError("LLM压缩待实现")

    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        # 简单的句子分割
        import re
        sentences = re.split(r'[。！？.!?\n]', text)
        return [s.strip() for s in sentences if s.strip()]

    def compress_batch(
        self,
        contents: List[str],
        query: str,
        max_length_per_item: int = 300
    ) -> List[CompressedContent]:
        """批量压缩"""
        return [
            self.compress(content, query, max_length_per_item)
            for content in contents
        ]


# 测试代码
if __name__ == "__main__":
    compressor = SemanticCompressor()

    test_content = """
    Transformer是一种基于自注意力机制的神经网络架构。它由Vaswani等人在2017年提出。
    Transformer完全摒弃了传统的循环神经网络结构。它使用多头注意力机制来捕获序列中的依赖关系。
    这种架构在机器翻译任务上取得了突破性的效果。后来BERT和GPT都基于Transformer架构。
    Transformer的核心是自注意力机制，它可以并行计算序列中所有位置的表示。
    这使得Transformer的训练速度大大快于RNN。
    """

    result = compressor.compress(
        test_content,
        query="Transformer注意力机制",
        max_length=200
    )

    print(f"原始长度: {result.original_length}")
    print(f"压缩后长度: {result.compressed_length}")
    print(f"压缩比: {result.compressed_length / result.original_length:.2%}")
    print(f"\n压缩内容:\n{result.content}")
    print(f"\n关键点: {result.key_points}")
