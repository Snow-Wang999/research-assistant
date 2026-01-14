"""Deep Research 模块

实现深度研究功能，包括：
- 子问题分解
- 并行搜索
- 报告生成
- v0.4.0: 全文研究（PDF 下载 + 筛选）
"""
from .decomposer import SubQuestionDecomposer
from .research_agent import ResearchAgent
from .fulltext_research_agent import FulltextResearchAgent
from .report_generator import ReportGenerator
from .orchestrator import DeepResearchOrchestrator, DeepResearchConfig, deep_research

__all__ = [
    "SubQuestionDecomposer",
    "ResearchAgent",
    "FulltextResearchAgent",
    "ReportGenerator",
    "DeepResearchOrchestrator",
    "DeepResearchConfig",
    "deep_research",
]
