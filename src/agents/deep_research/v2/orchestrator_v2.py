"""V2 协调器 - Deep Research V2 主入口

协调整个 V2 研究流程：
1. Supervisor 动态研究循环
2. 报告生成

与 V1 的区别：
- 无预设子问题分解
- 动态研究轮数
- 显式反思过程
"""
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass, field
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from utils.llm_client import QwenClient
from utils.logger import get_agent_logger

from .supervisor import SupervisorAgent, SupervisorResult
from .state import AgentState
from .prompts import build_report_prompt

log = get_agent_logger()


@dataclass
class DeepResearchV2Config:
    """V2 配置"""
    max_rounds: int = 10            # 最大研究轮数
    timeout_seconds: int = 300      # 超时时间（秒）
    use_fulltext: bool = False      # 是否使用全文（暂未实现）


@dataclass
class DeepResearchV2Output:
    """V2 输出"""
    # 原始查询
    query: str

    # Supervisor 状态
    state: AgentState

    # 研究报告（Markdown）
    report_markdown: str

    # 元数据
    metadata: Dict = field(default_factory=dict)

    @property
    def total_rounds(self) -> int:
        return self.state.current_round

    @property
    def total_sources(self) -> int:
        return len(self.state.get_all_sources())

    @property
    def thinking_history(self) -> List[str]:
        return self.state.thinking_history


class DeepResearchV2:
    """
    Deep Research V2 主入口

    使用 Supervisor 循环架构，动态决策研究轮数。

    使用方式：
    ```python
    research = DeepResearchV2(qwen_api_key="...")
    result = research.run("对比 Transformer 和 RNN")
    print(result.report_markdown)
    ```
    """

    def __init__(
        self,
        qwen_api_key: Optional[str] = None,
        config: Optional[DeepResearchV2Config] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ):
        """
        初始化 V2 协调器

        Args:
            qwen_api_key: 通义千问 API Key
            config: V2 配置
            progress_callback: 进度回调 (message, progress_ratio)
        """
        self.api_key = qwen_api_key
        self.config = config or DeepResearchV2Config()
        self.progress_callback = progress_callback

        self.llm_client = QwenClient(api_key=qwen_api_key) if qwen_api_key else None
        self.supervisor = SupervisorAgent(
            qwen_api_key=qwen_api_key,
            max_rounds=self.config.max_rounds,
            progress_callback=self._supervisor_progress
        )

    def _report_progress(self, message: str, progress: float):
        """报告进度"""
        if self.progress_callback:
            self.progress_callback(message, progress)
        log.info(f"[V2] {message} ({progress*100:.0f}%)")

    def _supervisor_progress(self, message: str, progress: float):
        """Supervisor 进度（映射到 0-80%）"""
        mapped_progress = progress * 0.8
        self._report_progress(message, mapped_progress)

    def run(self, query: str) -> DeepResearchV2Output:
        """
        执行深度研究

        Args:
            query: 用户查询

        Returns:
            DeepResearchV2Output: 研究输出
        """
        start_time = datetime.now()

        log.info(f"[V2] 开始深度研究: {query[:50]}...")
        self._report_progress("开始研究...", 0.0)

        try:
            # 阶段 1: Supervisor 研究循环
            supervisor_result = self.supervisor.run(query)
            state = supervisor_result.state

            # 阶段 2: 生成报告
            self._report_progress("正在生成研究报告...", 0.85)
            report_markdown = self._generate_report(query, state)

            # 计算耗时
            duration = (datetime.now() - start_time).total_seconds()

            self._report_progress("研究完成", 1.0)

            # 计算搜索和筛选统计
            total_searched = sum(len(rn.papers) for rn in state.raw_notes)
            total_selected = len(state.get_all_sources())

            # 构建元数据
            metadata = {
                "duration_seconds": duration,
                "total_rounds": supervisor_result.total_rounds,
                "completion_reason": supervisor_result.completion_reason,
                "total_searched": total_searched,  # 搜索到的论文总数
                "total_selected": total_selected,   # 筛选出的论文数
                "total_sources": total_selected,    # 兼容旧字段
                "thinking_count": len(state.thinking_history),
                "completed_at": datetime.now().isoformat(),
                "version": "v2"
            }

            return DeepResearchV2Output(
                query=query,
                state=state,
                report_markdown=report_markdown,
                metadata=metadata
            )

        except Exception as e:
            log.error(f"[V2] 研究出错: {e}")
            duration = (datetime.now() - start_time).total_seconds()

            # 返回错误报告
            error_report = f"""## ⚠️ 研究出错

**查询:** {query}

**错误信息:** {str(e)}

**耗时:** {duration:.1f} 秒

请稍后重试或简化查询。
"""
            return DeepResearchV2Output(
                query=query,
                state=AgentState(query=query),
                report_markdown=error_report,
                metadata={
                    "error": str(e),
                    "duration_seconds": duration
                }
            )

    def _generate_report(self, query: str, state: AgentState) -> str:
        """生成研究报告"""
        if not state.notes:
            return self._empty_report(query)

        if not self.llm_client:
            return self._fallback_report(query, state)

        try:
            # 构建 Prompt（传入来源列表用于统一编号）
            sources = state.get_all_sources()
            prompt = build_report_prompt(
                query=query,
                notes_summary=state.get_notes_summary(),
                thinking_history=state.thinking_history,
                sources=sources
            )

            # 调用 LLM 生成报告
            log.debug("[V2] 调用 LLM 生成报告...")
            report = self.llm_client.chat(
                prompt=prompt,
                task_type="report",
                max_tokens=3000,
                temperature=0.4,
                timeout=60.0
            )

            # 添加参考来源
            report += self._format_sources(state)

            return report

        except Exception as e:
            log.error(f"[V2] 报告生成出错: {e}")
            return self._fallback_report(query, state)

    def _format_sources(self, state: AgentState) -> str:
        """格式化参考来源"""
        sources = state.get_all_sources()
        if not sources:
            return ""

        lines = ["\n\n---\n\n## 参考来源\n"]
        for i, src in enumerate(sources, 1):
            authors = src.get("authors", [])
            author_str = ", ".join(authors[:2]) if authors else "Unknown"
            if len(authors) > 2:
                author_str += " et al."

            title = src.get("title", "Unknown")
            year = src.get("year", "N/A")
            url = src.get("url", "")
            source_type = src.get("source", "").upper()

            line = f"[{i}] {author_str}. *{title}*. {year}."
            if source_type:
                line += f" [{source_type}]"
            if url:
                line += f" [链接]({url})"

            lines.append(line)

        return "\n\n".join(lines)

    def _empty_report(self, query: str) -> str:
        """空报告"""
        return f"""## 研究报告

**查询:** {query}

**结果:** 未找到相关研究结果。

可能的原因：
1. 搜索关键词需要调整
2. 该领域论文较少
3. 请尝试使用更具体的术语

建议：尝试更换关键词或简化查询。
"""

    def _fallback_report(self, query: str, state: AgentState) -> str:
        """回退报告（无 LLM）"""
        report = f"""## 研究报告

**查询:** {query}

**研究轮数:** {state.current_round}

---

"""
        # 添加各轮笔记
        for note in state.notes:
            report += f"""### 第 {note.round_number} 轮: {note.topic}

**发现:** {note.findings}

**要点:**
"""
            for point in note.key_points:
                report += f"- {point}\n"

            report += "\n"

        # 添加来源
        report += self._format_sources(state)

        return report


# 便捷函数
def deep_research_v2(
    query: str,
    qwen_api_key: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    max_rounds: int = 10
) -> DeepResearchV2Output:
    """
    便捷函数：执行 V2 深度研究

    Args:
        query: 研究问题
        qwen_api_key: 通义千问 API Key
        progress_callback: 进度回调
        max_rounds: 最大研究轮数

    Returns:
        DeepResearchV2Output: 研究输出

    使用示例：
    ```python
    result = deep_research_v2("对比 GPT 和 Claude 的能力")
    print(result.report_markdown)
    print(f"研究轮数: {result.total_rounds}")
    ```
    """
    config = DeepResearchV2Config(max_rounds=max_rounds)
    research = DeepResearchV2(
        qwen_api_key=qwen_api_key,
        config=config,
        progress_callback=progress_callback
    )
    return research.run(query)


# 测试代码
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    print("=" * 60)
    print("Deep Research V2 测试")
    print("=" * 60)

    def progress_callback(msg, progress):
        bar_length = 30
        filled = int(bar_length * progress)
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"\r[{bar}] {progress*100:5.1f}% - {msg}", end="", flush=True)
        if progress >= 1.0:
            print()

    # 测试查询
    test_query = "对比 Transformer 和 RNN 在自然语言处理中的优劣势"

    # 使用便捷函数
    result = deep_research_v2(
        query=test_query,
        qwen_api_key=os.getenv("QWEN_API_KEY"),
        progress_callback=progress_callback,
        max_rounds=5
    )

    print("\n" + "=" * 60)
    print("研究报告")
    print("=" * 60)
    print(result.report_markdown)

    print("\n" + "=" * 60)
    print("元数据")
    print("=" * 60)
    for key, value in result.metadata.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 60)
    print("思考历史")
    print("=" * 60)
    for i, thought in enumerate(result.thinking_history, 1):
        print(f"{i}. {thought[:100]}...")
