"""V2 状态管理

实现 AgentState 和 reducer 模式，支持：
1. 消息追加（默认）
2. 状态覆盖（显式指定）
3. raw_notes / notes 分离
"""
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """对话消息"""
    role: MessageRole
    content: str
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """转换为 API 格式"""
        d = {"role": self.role.value, "content": self.content}
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        return d


@dataclass
class ResearchNote:
    """研究笔记（压缩后的发现）"""
    topic: str                      # 研究主题
    findings: str                   # 核心发现
    key_points: List[str]           # 关键要点
    sources: List[Dict]             # 来源论文（精简信息）
    round_number: int               # 第几轮研究
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class RawNote:
    """原始笔记（未压缩的完整数据）"""
    topic: str
    papers: List[Dict]              # 完整论文信息
    search_keywords: List[str]      # 使用的搜索关键词
    round_number: int
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class AgentState:
    """
    Agent 状态

    核心设计：
    1. messages: Supervisor 的对话历史
    2. notes: 压缩后的研究笔记（Supervisor 使用）
    3. raw_notes: 原始完整数据（外部存储，不进入 LLM）
    4. research_brief: 研究主题描述
    """
    # 原始查询
    query: str = ""

    # 研究简报（替代预设的子问题）
    research_brief: str = ""

    # 对话消息（Supervisor 视角）
    messages: List[Message] = field(default_factory=list)

    # 压缩后的研究笔记（用于 LLM 检索）
    notes: List[ResearchNote] = field(default_factory=list)

    # 原始完整数据（卸载到外部）
    raw_notes: List[RawNote] = field(default_factory=list)

    # 当前轮数
    current_round: int = 0

    # 最大轮数限制
    max_rounds: int = 10

    # 是否完成
    is_complete: bool = False

    # 完成原因
    completion_reason: str = ""

    # 思考历史（think_tool 输出）- 改为带轮次的结构
    # 格式: [{"round": 1, "thought": "..."}, ...]
    thinking_history: List[Dict[str, Any]] = field(default_factory=list)

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: MessageRole, content: str, **kwargs):
        """添加消息"""
        self.messages.append(Message(role=role, content=content, **kwargs))

    def add_note(self, note: ResearchNote):
        """添加研究笔记"""
        self.notes.append(note)
        self.current_round = max(self.current_round, note.round_number)

    def add_raw_note(self, raw_note: RawNote):
        """添加原始笔记（卸载）"""
        self.raw_notes.append(raw_note)

    def add_thinking(self, thought: str, round_number: int = 0):
        """添加思考记录（带轮次）"""
        self.thinking_history.append({
            "round": round_number,
            "thought": thought
        })

    def mark_complete(self, reason: str):
        """标记完成"""
        self.is_complete = True
        self.completion_reason = reason

    def get_notes_summary(self) -> str:
        """获取笔记摘要（用于报告生成）

        注意：不显示轮次编号，按主题组织内容
        """
        if not self.notes:
            return "尚无研究发现。"

        parts = []
        for note in self.notes:
            # 不显示轮次，只按主题组织
            parts.append(
                f"### {note.topic}\n\n"
                f"**发现：** {note.findings}\n\n"
                f"**要点：**\n" +
                "\n".join([f"- {p}" for p in note.key_points]) +
                "\n"
            )
        return "\n---\n\n".join(parts)

    def get_all_sources(self) -> List[Dict]:
        """获取所有来源论文（去重）"""
        seen_titles = set()
        sources = []
        for note in self.notes:
            for src in note.sources:
                title = src.get("title", "").lower().strip()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    sources.append(src)
        return sources


class StateReducer:
    """
    状态 Reducer

    支持两种更新模式：
    1. append: 追加（默认）
    2. override: 覆盖
    """

    @staticmethod
    def reduce(
        current_state: AgentState,
        updates: Dict[str, Any]
    ) -> AgentState:
        """
        应用状态更新

        Args:
            current_state: 当前状态
            updates: 更新内容
                - 普通值：直接覆盖
                - {"type": "append", "value": ...}：追加到列表
                - {"type": "override", "value": ...}：显式覆盖

        Returns:
            更新后的状态（原地修改）
        """
        for key, value in updates.items():
            if not hasattr(current_state, key):
                continue

            current_value = getattr(current_state, key)

            # 处理特殊更新格式
            if isinstance(value, dict) and "type" in value:
                update_type = value["type"]
                update_value = value.get("value")

                if update_type == "append" and isinstance(current_value, list):
                    if isinstance(update_value, list):
                        current_value.extend(update_value)
                    else:
                        current_value.append(update_value)
                elif update_type == "override":
                    setattr(current_state, key, update_value)
            else:
                # 列表默认追加，其他直接覆盖
                if isinstance(current_value, list) and isinstance(value, list):
                    current_value.extend(value)
                else:
                    setattr(current_state, key, value)

        return current_state


# 便捷函数
def create_initial_state(query: str, research_brief: str = "") -> AgentState:
    """
    创建初始状态

    Args:
        query: 用户查询
        research_brief: 研究简报（可选）

    Returns:
        初始化的 AgentState
    """
    brief = research_brief or f"研究主题：{query}\n\n请围绕这个主题进行深入研究，探索相关概念、最新进展和关键发现。"

    return AgentState(
        query=query,
        research_brief=brief,
        metadata={
            "created_at": datetime.now().isoformat(),
            "query": query
        }
    )


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("V2 状态管理测试")
    print("=" * 60)

    # 创建初始状态
    state = create_initial_state("对比 Transformer 和 RNN")
    print(f"初始状态: query={state.query}")
    print(f"research_brief={state.research_brief[:50]}...")

    # 添加消息
    state.add_message(MessageRole.USER, "开始研究")
    state.add_message(MessageRole.ASSISTANT, "好的，我来分析...")
    print(f"\n消息数: {len(state.messages)}")

    # 添加研究笔记
    note = ResearchNote(
        topic="Transformer 基础",
        findings="Transformer 使用自注意力机制...",
        key_points=["注意力机制", "并行计算", "位置编码"],
        sources=[{"title": "Attention is All You Need", "year": 2017}],
        round_number=1
    )
    state.add_note(note)
    print(f"\n笔记数: {len(state.notes)}")
    print(f"笔记摘要:\n{state.get_notes_summary()}")

    # 使用 reducer 更新
    StateReducer.reduce(state, {
        "current_round": 2,
    })
    # 使用 add_thinking 方法添加思考（带轮次）
    state.add_thinking("需要更多对比数据", round_number=2)
    print(f"\n当前轮数: {state.current_round}")
    print(f"思考历史: {state.thinking_history}")

    # 标记完成
    state.mark_complete("研究充分")
    print(f"\n是否完成: {state.is_complete}")
    print(f"完成原因: {state.completion_reason}")
