"""摘要总结器 - 使用LLM将英文摘要总结为中文，并翻译标题"""
import json
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.llm_client import QwenClient


class AbstractSummarizer:
    """使用LLM总结论文摘要并翻译标题"""

    def __init__(
        self,
        qwen_api_key: str = "",
        max_workers: int = 5,
    ):
        self.llm_client = QwenClient(api_key=qwen_api_key) if qwen_api_key else None
        self.max_workers = max_workers

        if not self.llm_client:
            print("[摘要总结] 未配置 QWEN_API_KEY，将显示原始摘要")

    def summarize_and_translate(self, abstract: str, title: str = "") -> dict:
        """
        总结摘要并翻译标题（一次API调用完成）

        Args:
            abstract: 原始摘要（英文）
            title: 论文标题（英文）

        Returns:
            dict: {"title_cn": "中文标题", "summary": "中文摘要总结"}
        """
        if not self.llm_client:
            return {
                "title_cn": "",
                "summary": abstract[:200] + "..." if len(abstract) > 200 else abstract
            }

        if not abstract or abstract == "无摘要":
            abstract_text = ""
        else:
            abstract_text = abstract

        prompt = f"""请完成以下两个任务，返回JSON格式：

1. 将论文标题翻译为中文（简洁准确）
2. 将摘要总结为中文（50字以内，保留核心贡献）

论文标题：{title}
摘要：{abstract_text or "无"}

请返回JSON格式（不要有其他内容）：
{{"title_cn": "中文标题", "summary": "中文摘要总结"}}"""

        try:
            # 使用通义千问 turbo 模型（翻译总结是简单任务）
            content = self.llm_client.chat(
                prompt=prompt,
                task_type="compress",
                max_tokens=200,
                temperature=0.3,
                timeout=20.0
            )

            # 解析JSON
            # 处理可能的markdown代码块
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            parsed = json.loads(content)
            return {
                "title_cn": parsed.get("title_cn", ""),
                "summary": parsed.get("summary", abstract[:150] if abstract else "暂无摘要")
            }
        except json.JSONDecodeError:
            # JSON解析失败，返回原始内容作为摘要
            return {
                "title_cn": "",
                "summary": content if 'content' in dir() else (abstract[:150] if abstract else "")
            }
        except Exception as e:
            print(f"[摘要总结] 失败: {e}")
            return {
                "title_cn": "",
                "summary": abstract[:150] + "..." if abstract and len(abstract) > 150 else (abstract or "")
            }

    def summarize_batch(self, papers: List[dict]) -> List[dict]:
        """
        批量总结论文摘要并翻译标题（并行处理）

        Args:
            papers: 论文列表，每个包含 'abstract' 和 'title' 字段

        Returns:
            添加了 'summary' 和 'title_cn' 字段的论文列表
        """
        if not self.api_key:
            # 无API Key时直接返回原始数据
            for paper in papers:
                paper['summary'] = paper.get('abstract', '')[:200]
                paper['title_cn'] = ""
            return papers

        def process_paper(paper):
            abstract = paper.get('abstract', '')
            title = paper.get('title', '')
            result = self.summarize_and_translate(abstract, title)
            paper['summary'] = result['summary']
            paper['title_cn'] = result['title_cn']
            return paper

        # 并行处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(process_paper, p): p for p in papers}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    paper = futures[future]
                    paper['summary'] = paper.get('abstract', '')[:150]
                    paper['title_cn'] = ""

        return papers


# 测试代码
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    summarizer = AbstractSummarizer(
        qwen_api_key=os.getenv("QWEN_API_KEY", "")
    )

    test_abstract = """
    We introduce a new language representation model called BERT, which stands for
    Bidirectional Encoder Representations from Transformers. Unlike recent language
    representation models, BERT is designed to pre-train deep bidirectional
    representations from unlabeled text by jointly conditioning on both left and
    right context in all layers. As a result, the pre-trained BERT model can be
    fine-tuned with just one additional output layer to create state-of-the-art
    models for a wide range of tasks, such as question answering and language
    inference, without substantial task-specific architecture modifications.
    """

    print("原始摘要:")
    print(test_abstract)
    print("\n" + "=" * 50)
    print("中文总结:")
    summary = summarizer.summarize(test_abstract, "BERT: Pre-training of Deep Bidirectional Transformers")
    print(summary)
