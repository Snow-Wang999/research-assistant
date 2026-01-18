"""V2 工具定义

Supervisor 可用的三个核心工具：
1. think_tool - 显式反思，规划下一步
2. ConductResearch - 派发研究任务给 Researcher
3. ResearchComplete - 标记研究完成
"""
from typing import List, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum


class SearchStrategy(str, Enum):
    """搜索策略"""
    BROAD = "broad"       # 广泛搜索（探索阶段）
    FOCUSED = "focused"   # 聚焦搜索（深入阶段）
    COMPARISON = "comparison"  # 对比搜索（对比分析）


@dataclass
class ThinkTool:
    """
    思考工具

    让 Supervisor 显式进行反思和规划。
    输出会被记录到状态中，用于追踪决策过程。

    使用场景：
    - 开始研究时：规划研究方向
    - 收到研究结果后：评估是否充分，决定下一步
    - 遇到困难时：调整策略
    """
    thought: str  # 思考内容

    def __str__(self):
        return f"[Think] {self.thought}"


@dataclass
class ConductResearch:
    """
    派发研究任务

    Supervisor 使用此工具派发研究任务给 Researcher。
    Researcher 会执行搜索、筛选、压缩，返回核心发现。

    参数说明：
    - topic: 研究主题（具体、可搜索）
    - search_keywords: 搜索关键词列表（2-4个）
    - strategy: 搜索策略
    - focus_points: 重点关注的方面（可选）
    """
    topic: str                      # 研究主题
    search_keywords: List[str]      # 搜索关键词
    strategy: SearchStrategy = SearchStrategy.BROAD
    focus_points: Optional[List[str]] = None  # 重点关注

    def __post_init__(self):
        # 确保关键词列表有效
        if not self.search_keywords:
            self.search_keywords = [self.topic]
        # 限制关键词数量
        self.search_keywords = self.search_keywords[:4]

    def __str__(self):
        keywords = ", ".join(self.search_keywords)
        return f"[Research] {self.topic} (keywords: {keywords}, strategy: {self.strategy.value})"


@dataclass
class ResearchComplete:
    """
    标记研究完成

    Supervisor 使用此工具标记研究已完成。
    调用后将退出研究循环，进入报告生成阶段。

    参数说明：
    - reason: 完成原因（用于日志和调试）
    - summary: 研究总结（可选）
    """
    reason: str  # 完成原因
    summary: Optional[str] = None  # 研究总结

    def __str__(self):
        return f"[Complete] {self.reason}"


# 工具 Schema 定义（用于 LLM Function Calling）
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "think",
            "description": "显式思考和规划。在决定下一步行动之前，先思考当前状态和策略。每次研究前后都应该思考。",
            "parameters": {
                "type": "object",
                "properties": {
                    "thought": {
                        "type": "string",
                        "description": "你的思考内容。包括：当前研究状态、已获得的发现、还需要什么信息、下一步计划"
                    }
                },
                "required": ["thought"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "conduct_research",
            "description": "派发研究任务。指定研究主题和关键词，Researcher 会搜索论文并返回压缩后的核心发现。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "研究主题。应该具体、可搜索，例如：'Transformer 的自注意力机制原理'"
                    },
                    "search_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "搜索关键词列表（2-4个）。使用学术术语，如：['Transformer self-attention', 'attention mechanism NLP']"
                    },
                    "strategy": {
                        "type": "string",
                        "enum": ["broad", "focused", "comparison"],
                        "description": "搜索策略：broad=广泛探索，focused=深入聚焦，comparison=对比分析"
                    },
                    "focus_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "重点关注的方面（可选）。如：['性能对比', '计算效率', '应用场景']"
                    }
                },
                "required": ["topic", "search_keywords"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "research_complete",
            "description": "标记研究完成。当你认为已经收集到足够的信息来回答用户问题时调用。调用后将生成研究报告。",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "完成原因。说明为什么认为研究已经充分。如：'已覆盖所有对比维度，收集到足够的证据'"
                    },
                    "summary": {
                        "type": "string",
                        "description": "研究总结（可选）。简要概括主要发现，用于生成报告。"
                    }
                },
                "required": ["reason"]
            }
        }
    }
]


def parse_tool_call(tool_name: str, arguments: dict) -> Optional[object]:
    """
    解析工具调用

    Args:
        tool_name: 工具名称
        arguments: 工具参数

    Returns:
        工具对象，或 None（无法解析）
    """
    if tool_name == "think":
        return ThinkTool(thought=arguments.get("thought", ""))

    elif tool_name == "conduct_research":
        strategy_str = arguments.get("strategy", "broad")
        try:
            strategy = SearchStrategy(strategy_str)
        except ValueError:
            strategy = SearchStrategy.BROAD

        return ConductResearch(
            topic=arguments.get("topic", ""),
            search_keywords=arguments.get("search_keywords", []),
            strategy=strategy,
            focus_points=arguments.get("focus_points")
        )

    elif tool_name == "research_complete":
        return ResearchComplete(
            reason=arguments.get("reason", ""),
            summary=arguments.get("summary")
        )

    return None


def get_tool_names() -> List[str]:
    """获取所有工具名称"""
    return ["think", "conduct_research", "research_complete"]


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("V2 工具定义测试")
    print("=" * 60)

    # 测试 ThinkTool
    think = ThinkTool(thought="需要先了解 Transformer 的基础，再进行对比")
    print(f"\n{think}")

    # 测试 ConductResearch
    research = ConductResearch(
        topic="Transformer 自注意力机制",
        search_keywords=["Transformer self-attention", "attention mechanism"],
        strategy=SearchStrategy.FOCUSED,
        focus_points=["并行计算", "位置编码"]
    )
    print(f"\n{research}")

    # 测试 ResearchComplete
    complete = ResearchComplete(
        reason="已收集到足够的对比数据",
        summary="Transformer 在并行性和长距离依赖上优于 RNN"
    )
    print(f"\n{complete}")

    # 测试解析
    print("\n--- 工具解析测试 ---")
    parsed = parse_tool_call("conduct_research", {
        "topic": "RNN 序列建模",
        "search_keywords": ["RNN sequence modeling", "LSTM"]
    })
    print(f"解析结果: {parsed}")

    # 打印 Schema
    print("\n--- 工具 Schema ---")
    import json
    for schema in TOOL_SCHEMAS:
        print(f"\n{schema['function']['name']}:")
        print(json.dumps(schema, indent=2, ensure_ascii=False)[:200] + "...")
