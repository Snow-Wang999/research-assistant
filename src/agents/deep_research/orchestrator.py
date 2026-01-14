"""深度研究协调器

协调整个深度研究流程：
1. 问题分解
2. 并行研究
3. 报告生成

这是 Deep Research 功能的主入口。
"""
from typing import Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from .decomposer import SubQuestionDecomposer, DecompositionResult
from .research_agent import ResearchAgent, ResearchResult, ParallelResearchRunner
from .fulltext_research_agent import FulltextResearchAgent, FulltextResearchResult, ParallelFulltextResearchRunner
from .report_generator import ReportGenerator, ResearchReport


@dataclass
class DeepResearchConfig:
    """深度研究配置"""
    max_sub_questions: int = 3          # 最大子问题数
    papers_per_question: int = 30       # 每个子问题搜索的论文数（增加搜索量）
    max_parallel_workers: int = 5       # 最大并行数
    enable_compression: bool = True     # 是否启用 LLM 压缩
    timeout_seconds: int = 180          # 整体超时时间（秒），增加以适应更多搜索
    # v0.4.0 新增：全文研究选项
    use_fulltext: bool = False          # 是否使用全文研究（下载 PDF）
    max_fulltext_per_question: int = 10 # 每个子问题最多获取的全文数
    papers_to_analyze: int = 10         # 筛选后用于分析的论文数


@dataclass
class DeepResearchOutput:
    """深度研究输出"""
    # 原始查询
    query: str

    # 分解结果
    decomposition: DecompositionResult

    # 各子问题的研究结果
    research_results: list  # List[ResearchResult]

    # 最终报告
    report: ResearchReport

    # Markdown 格式报告
    report_markdown: str

    # 元数据
    metadata: dict = field(default_factory=dict)


class DeepResearchOrchestrator:
    """
    深度研究协调器

    协调整个深度研究流程，类似 Open Deep Research 的主图。

    使用方式：
    ```python
    orchestrator = DeepResearchOrchestrator(qwen_api_key="...")
    result = orchestrator.run("对比 Transformer 和 RNN")
    print(result.report_markdown)
    ```
    """

    def __init__(
        self,
        qwen_api_key: Optional[str] = None,
        config: Optional[DeepResearchConfig] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ):
        """
        初始化协调器

        Args:
            qwen_api_key: 通义千问 API Key
            config: 研究配置
            progress_callback: 进度回调函数 (message, progress_ratio)
        """
        self.api_key = qwen_api_key
        self.config = config or DeepResearchConfig()
        self.progress_callback = progress_callback

        # 初始化各组件
        self.decomposer = SubQuestionDecomposer(qwen_api_key=qwen_api_key)

        # 根据配置选择研究模式
        if self.config.use_fulltext:
            # v0.4.0: 全文研究模式
            self.research_runner = ParallelFulltextResearchRunner(
                qwen_api_key=qwen_api_key,
                max_workers=min(2, self.config.max_parallel_workers),  # 全文模式减少并发
                max_fulltext_per_question=self.config.max_fulltext_per_question
            )
            self.use_fulltext = True
        else:
            # 原有摘要研究模式
            self.research_runner = ParallelResearchRunner(
                qwen_api_key=qwen_api_key,
                max_workers=self.config.max_parallel_workers
            )
            self.use_fulltext = False

        self.report_generator = ReportGenerator(qwen_api_key=qwen_api_key)

    def _report_progress(self, message: str, progress: float):
        """报告进度"""
        if self.progress_callback:
            self.progress_callback(message, progress)
        print(f"[DeepResearch] {message} ({progress*100:.0f}%)")

    def _check_timeout(self, start_time: datetime, stage: str):
        """检查是否超时"""
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed > self.config.timeout_seconds:
            raise TimeoutError(f"深度研究超时（{elapsed:.0f}秒 > {self.config.timeout_seconds}秒），阶段: {stage}")

    def run(self, query: str) -> DeepResearchOutput:
        """
        执行深度研究

        Args:
            query: 用户的研究问题

        Returns:
            DeepResearchOutput: 完整的研究输出
        """
        start_time = datetime.now()

        # 记录各阶段耗时
        stage_times = {}

        try:
            # 阶段 1: 问题分解 (0-20%)
            stage_start = datetime.now()
            self._report_progress("正在分析问题...", 0.0)
            decomposition = self.decomposer.decompose(query)
            stage_times["1_问题分解"] = (datetime.now() - stage_start).total_seconds()
            self._check_timeout(start_time, "问题分解")

            # 限制子问题数量
            if len(decomposition.sub_questions) > self.config.max_sub_questions:
                decomposition.sub_questions = decomposition.sub_questions[:self.config.max_sub_questions]

            self._report_progress(
                f"分解为 {len(decomposition.sub_questions)} 个子问题 ({stage_times['1_问题分解']:.1f}s)",
                0.2
            )

            # 阶段 2: 并行研究 (20-70%)
            stage_start = datetime.now()
            if self.use_fulltext:
                self._report_progress("正在搜索论文并获取全文...", 0.25)
            else:
                self._report_progress("正在搜索相关论文...", 0.25)
            self._check_timeout(start_time, "搜索前")

            research_results = self.research_runner.run(
                sub_questions=decomposition.sub_questions,
                limit_per_question=self.config.papers_per_question
            )
            stage_times["2_论文搜索"] = (datetime.now() - stage_start).total_seconds()
            self._check_timeout(start_time, "搜索后")

            # 统计论文数量
            if self.use_fulltext:
                total_papers = sum(r.papers_searched for r in research_results)
                fulltext_papers = sum(r.papers_with_fulltext for r in research_results)
                self._report_progress(
                    f"完成搜索，共 {total_papers} 篇论文，获取 {fulltext_papers} 篇全文 ({stage_times['2_论文搜索']:.1f}s)",
                    0.7
                )
            else:
                total_papers = sum(r.papers_found for r in research_results)
                self._report_progress(
                    f"完成搜索，共找到 {total_papers} 篇论文 ({stage_times['2_论文搜索']:.1f}s)",
                    0.7
                )

            # 阶段 3: 报告生成 (70-100%)
            stage_start = datetime.now()
            self._report_progress("正在生成研究报告...", 0.75)
            self._check_timeout(start_time, "报告生成前")

            report = self.report_generator.generate(decomposition, research_results)
            report_markdown = self.report_generator.format_as_markdown(report)
            stage_times["3_报告生成"] = (datetime.now() - stage_start).total_seconds()

            # 计算耗时
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            self._report_progress(f"研究完成，耗时 {duration:.1f} 秒", 1.0)

            # 构建元数据
            metadata = {
                "duration_seconds": duration,
                "sub_questions_count": len(decomposition.sub_questions),
                "total_papers": total_papers,
                "query_type": decomposition.query_type,
                "completed_at": end_time.isoformat(),
                "stage_times": stage_times,
                "use_fulltext": self.use_fulltext  # v0.4.0: 标记研究模式
            }

            # 全文模式额外统计
            if self.use_fulltext:
                metadata["fulltext_papers"] = fulltext_papers
                metadata["screened_papers"] = sum(r.papers_screened for r in research_results)

            return DeepResearchOutput(
                query=query,
                decomposition=decomposition,
                research_results=research_results,
                report=report,
                report_markdown=report_markdown,
                metadata=metadata
            )

        except TimeoutError as e:
            # 超时处理：返回部分结果
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self._report_progress(f"研究超时 ({duration:.0f}秒)", 1.0)

            # 返回空结果
            empty_decomposition = DecompositionResult(
                original_query=query,
                query_type="timeout",
                sub_questions=[],
                research_strategy="研究超时"
            )
            empty_report = self.report_generator._empty_report(query)
            empty_report.overview = f"⚠️ 研究超时（{duration:.0f}秒），请稍后重试或简化查询。"

            return DeepResearchOutput(
                query=query,
                decomposition=empty_decomposition,
                research_results=[],
                report=empty_report,
                report_markdown=f"## ⚠️ 研究超时\n\n耗时 {duration:.0f} 秒，超过限制 {self.config.timeout_seconds} 秒。\n\n请稍后重试或简化查询。",
                metadata={
                    "duration_seconds": duration,
                    "error": str(e),
                    "timeout": True
                }
            )

    def run_with_existing_decomposition(
        self,
        query: str,
        decomposition: DecompositionResult
    ) -> DeepResearchOutput:
        """
        使用已有的问题分解执行研究

        适用于用户手动调整子问题后重新研究的场景。
        """
        start_time = datetime.now()

        # 跳过分解阶段
        self._report_progress("使用已有分解，开始搜索...", 0.2)

        # 执行研究
        research_results = self.research_runner.run(
            sub_questions=decomposition.sub_questions,
            limit_per_question=self.config.papers_per_question
        )

        total_papers = sum(r.papers_found for r in research_results)
        self._report_progress(f"完成搜索，共找到 {total_papers} 篇论文", 0.7)

        # 生成报告
        self._report_progress("正在生成研究报告...", 0.75)

        report = self.report_generator.generate(decomposition, research_results)
        report_markdown = self.report_generator.format_as_markdown(report)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        self._report_progress(f"研究完成，耗时 {duration:.1f} 秒", 1.0)

        return DeepResearchOutput(
            query=query,
            decomposition=decomposition,
            research_results=research_results,
            report=report,
            report_markdown=report_markdown,
            metadata={
                "duration_seconds": duration,
                "sub_questions_count": len(decomposition.sub_questions),
                "total_papers": total_papers,
                "query_type": decomposition.query_type,
                "completed_at": end_time.isoformat()
            }
        )


# 便捷函数
def deep_research(
    query: str,
    qwen_api_key: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    use_fulltext: bool = False  # v0.4.0: 全文研究模式
) -> DeepResearchOutput:
    """
    便捷函数：执行深度研究

    Args:
        query: 研究问题
        qwen_api_key: 通义千问 API Key
        progress_callback: 进度回调
        use_fulltext: 是否使用全文研究（下载 PDF）

    Returns:
        DeepResearchOutput: 研究输出

    使用示例：
    ```python
    # 摘要模式（快速）
    result = deep_research("对比 GPT 和 Claude 的能力")

    # 全文模式（深入，需要更多时间）
    result = deep_research("Transformer 架构分析", use_fulltext=True)

    print(result.report_markdown)
    ```
    """
    config = DeepResearchConfig(
        use_fulltext=use_fulltext,
        timeout_seconds=180 if use_fulltext else 120  # 全文模式更长超时
    )
    orchestrator = DeepResearchOrchestrator(
        qwen_api_key=qwen_api_key,
        config=config,
        progress_callback=progress_callback
    )
    return orchestrator.run(query)


# 测试代码
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    print("=" * 60)
    print("深度研究协调器测试")
    print("=" * 60)

    # 测试查询
    test_query = "对比 Transformer 和 RNN 在自然语言处理中的应用"

    # 使用便捷函数
    result = deep_research(
        query=test_query,
        qwen_api_key=os.getenv("QWEN_API_KEY")
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
