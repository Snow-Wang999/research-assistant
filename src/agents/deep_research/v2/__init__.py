"""Deep Research V2 - 基于 Supervisor 循环的动态研究架构

V2 架构核心改进：
1. Supervisor 循环：动态决策研究轮数，而非固定3轮
2. Subagent as Tool：Researcher 作为工具调用，返回压缩结果
3. 显式反思：think_tool 让思考过程可见
4. 状态管理：AgentState + reducer 统一管理

使用方式：
```python
from agents.deep_research.v2 import DeepResearchV2

research = DeepResearchV2(qwen_api_key="...")
result = research.run("对比 Transformer 和 RNN 的优劣")
print(result.report_markdown)
```
"""
from .orchestrator_v2 import DeepResearchV2, DeepResearchV2Config, deep_research_v2
from .supervisor import SupervisorAgent
from .researcher import Researcher, CompressedResearch
from .state import AgentState, ResearchNote
from .tools import ConductResearch, ResearchComplete, ThinkTool

__all__ = [
    "DeepResearchV2",
    "DeepResearchV2Config",
    "deep_research_v2",
    "SupervisorAgent",
    "Researcher",
    "CompressedResearch",
    "AgentState",
    "ResearchNote",
    "ConductResearch",
    "ResearchComplete",
    "ThinkTool",
]
