"""阅读导航 - 根据搜索结果生成论文阅读建议"""
import json
import re
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.llm_client import QwenClient


class ReadingGuide:
    """
    阅读导航生成器

    根据搜索到的论文列表，生成阅读建议：
    - 入门必读
    - 核心论文
    - 最新进展
    - 阅读顺序建议
    """

    SYSTEM_PROMPT = """你是一个学术论文阅读顾问。根据用户的研究问题和搜索到的论文列表，生成简洁的阅读建议。

任务：分析论文列表，推荐阅读顺序，并对所有论文进行主题分类。

论文来源说明：
- [ARXIV]: 来自 arXiv 的最新预印本论文
- [OPENALEX]: 来自 OpenAlex 的高引用经典论文

输出 JSON 格式（不要输出其他内容）：
{
  "summary": "这些论文的整体概述（1-2句话）",
  "entry_point": {
    "index": 论文序号,
    "reason": "为什么从这篇开始（15字内）"
  },
  "core_papers": [
    {"index": 序号, "reason": "推荐理由（15字内）"}
  ],
  "latest": {
    "index": 序号,
    "reason": "值得关注的原因（15字内）"
  },
  "reading_order": [序号1, 序号2, ...],
  "categories": [
    {
      "name": "分类名称（如：理论基础/方法改进/应用场景/综述）",
      "papers": [序号1, 序号2, ...],
      "description": "这类论文的简要说明（15字内）"
    }
  ]
}

规则：
- entry_point: 选1篇最适合入门的论文（通常是高引用经典论文，优先考虑 OPENALEX）
- core_papers: 选2-3篇最重要的论文，需同时包含 ARXIV 和 OPENALEX 的论文
- latest: 选1篇最新的进展（优先考虑 ARXIV 的新论文）
- reading_order: 推荐的阅读顺序，应涵盖两个来源的论文
- categories: 将所有论文按主题分成3-5类，每篇论文只归入一类
- 序号从1开始
- 理由要简洁"""

    def __init__(self, qwen_api_key: Optional[str] = None):
        self.llm_client = QwenClient(api_key=qwen_api_key) if qwen_api_key else None

    def _format_papers_for_prompt(self, papers: list) -> str:
        """格式化论文列表用于 prompt"""
        lines = []
        for i, p in enumerate(papers, 1):
            source = p.get('source', 'unknown').upper()
            year = p.get('year', 'N/A')
            citations = p.get('citation_count', 0) or 0
            abstract = p.get('abstract', '')[:200] if p.get('abstract') else ''
            lines.append(
                f"[{i}] [{source}] {p['title']}\n"
                f"    年份: {year}, 引用: {citations}\n"
                f"    摘要: {abstract}..."
            )
        return "\n".join(lines)

    def _parse_response(self, content: str) -> dict:
        """解析 LLM 响应"""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def generate(self, query: str, papers: list) -> dict:
        """
        生成阅读导航

        Args:
            query: 用户的研究问题
            papers: 论文列表

        Returns:
            阅读建议字典
        """
        if not papers:
            return {"error": "没有论文可分析"}

        if not self.llm_client:
            return self._fallback_guide(papers)

        try:
            papers_text = self._format_papers_for_prompt(papers)

            # 使用通义千问 turbo 模型（阅读导航是简单分类任务）
            prompt = f"{self.SYSTEM_PROMPT}\n\n研究问题: {query}\n\n论文列表:\n{papers_text}"
            content = self.llm_client.chat(
                prompt=prompt,
                task_type="screen",
                max_tokens=500,
                temperature=0.3,
                timeout=30.0
            )

            parsed = self._parse_response(content)

            if parsed:
                return self._format_guide(parsed, papers)
            else:
                return self._fallback_guide(papers)

        except Exception as e:
            print(f"[ReadingGuide] 生成出错: {e}")
            return self._fallback_guide(papers)

    def _fallback_guide(self, papers: list) -> dict:
        """回退方案：基于规则的简单推荐"""
        if not papers:
            return {"error": "没有论文"}

        # 按引用数排序找核心论文
        sorted_by_citations = sorted(
            enumerate(papers, 1),
            key=lambda x: x[1].get('citation_count', 0) or 0,
            reverse=True
        )

        # 按年份排序找最新
        sorted_by_year = sorted(
            enumerate(papers, 1),
            key=lambda x: x[1].get('year', 0) or 0,
            reverse=True
        )

        entry = sorted_by_citations[0] if sorted_by_citations else None
        core = sorted_by_citations[:3]
        latest = sorted_by_year[0] if sorted_by_year else None

        return {
            "summary": f"共找到 {len(papers)} 篇相关论文",
            "entry_point": {
                "index": entry[0] if entry else 1,
                "title": entry[1]['title'] if entry else "",
                "reason": "高引用，适合入门"
            } if entry else None,
            "core_papers": [
                {
                    "index": idx,
                    "title": p['title'],
                    "reason": f"引用数 {p.get('citation_count', 0)}"
                }
                for idx, p in core[:2]
            ],
            "latest": {
                "index": latest[0] if latest else 1,
                "title": latest[1]['title'] if latest else "",
                "reason": f"{latest[1].get('year', '')} 年发表"
            } if latest else None,
            "reading_order": [x[0] for x in sorted_by_citations[:5]]
        }

    def _format_guide(self, parsed: dict, papers: list) -> dict:
        """格式化 LLM 返回的结果，添加论文标题"""
        result = {
            "summary": parsed.get("summary", ""),
            "reading_order": parsed.get("reading_order", [])
        }

        # 入门推荐
        if parsed.get("entry_point"):
            idx = parsed["entry_point"].get("index", 1)
            if 1 <= idx <= len(papers):
                result["entry_point"] = {
                    "index": idx,
                    "title": papers[idx - 1]["title"],
                    "reason": parsed["entry_point"].get("reason", "")
                }

        # 核心论文
        result["core_papers"] = []
        for cp in parsed.get("core_papers", []):
            idx = cp.get("index", 1)
            if 1 <= idx <= len(papers):
                result["core_papers"].append({
                    "index": idx,
                    "title": papers[idx - 1]["title"],
                    "reason": cp.get("reason", "")
                })

        # 最新进展
        if parsed.get("latest"):
            idx = parsed["latest"].get("index", 1)
            if 1 <= idx <= len(papers):
                result["latest"] = {
                    "index": idx,
                    "title": papers[idx - 1]["title"],
                    "reason": parsed["latest"].get("reason", "")
                }

        # 论文分类
        result["categories"] = []
        for cat in parsed.get("categories", []):
            category = {
                "name": cat.get("name", "其他"),
                "description": cat.get("description", ""),
                "papers": []
            }
            for idx in cat.get("papers", []):
                if 1 <= idx <= len(papers):
                    category["papers"].append({
                        "index": idx,
                        "title": papers[idx - 1]["title"]
                    })
            if category["papers"]:
                result["categories"].append(category)

        return result

    def format_for_display(self, guide: dict) -> str:
        """格式化为显示文本"""
        if guide.get("error"):
            return f"⚠️ {guide['error']}"

        lines = ["📚 **阅读建议**\n"]

        if guide.get("summary"):
            lines.append(f"{guide['summary']}\n")

        if guide.get("entry_point"):
            ep = guide["entry_point"]
            lines.append(f"🌟 **入门必读**")
            lines.append(f"   [{ep['index']}] {ep['title'][:50]}...")
            lines.append(f"   → {ep['reason']}\n")

        if guide.get("core_papers"):
            lines.append(f"📌 **核心论文**")
            for cp in guide["core_papers"]:
                lines.append(f"   [{cp['index']}] {cp['title'][:50]}...")
                lines.append(f"   → {cp['reason']}")
            lines.append("")

        if guide.get("latest"):
            lt = guide["latest"]
            lines.append(f"🆕 **最新进展**")
            lines.append(f"   [{lt['index']}] {lt['title'][:50]}...")
            lines.append(f"   → {lt['reason']}\n")

        if guide.get("reading_order"):
            order = guide["reading_order"][:5]
            lines.append(f"📖 **推荐阅读顺序**: {' → '.join(map(str, order))}")

        return "\n".join(lines)


# 测试代码
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    guide_gen = ReadingGuide(
        qwen_api_key=os.getenv("QWEN_API_KEY")
    )

    # 模拟论文数据
    test_papers = [
        {
            "title": "Attention Is All You Need",
            "year": 2017,
            "citation_count": 50000,
            "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks..."
        },
        {
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "year": 2018,
            "citation_count": 40000,
            "abstract": "We introduce a new language representation model called BERT..."
        },
        {
            "title": "GPT-4 Technical Report",
            "year": 2023,
            "citation_count": 2000,
            "abstract": "We report the development of GPT-4, a large-scale, multimodal model..."
        },
    ]

    print("=" * 60)
    print("阅读导航测试")
    print("=" * 60)

    guide = guide_gen.generate("Transformer架构的发展", test_papers)
    print(guide_gen.format_for_display(guide))
