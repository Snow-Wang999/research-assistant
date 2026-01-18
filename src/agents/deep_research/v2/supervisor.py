"""V2 Supervisor Agent - 研究主管

核心循环：
while not complete:
    1. think() - 反思当前状态
    2. conduct_research() 或 research_complete()
    3. 更新状态

关键设计：
- 动态决策研究轮数（而非固定3轮）
- 显式反思（think_tool）
- 工具调用（Function Calling）
"""
import json
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from utils.llm_client import QwenClient
from utils.logger import get_agent_logger

from .state import AgentState, MessageRole, ResearchNote, RawNote, create_initial_state
from .tools import (
    ThinkTool, ConductResearch, ResearchComplete,
    TOOL_SCHEMAS, parse_tool_call, SearchStrategy
)
from .prompts import SUPERVISOR_SYSTEM_PROMPT, SUPERVISOR_START_PROMPT
from .researcher import Researcher, CompressedResearch, RawResearchData

log = get_agent_logger()


@dataclass
class SupervisorResult:
    """Supervisor 运行结果"""
    state: AgentState               # 最终状态
    total_rounds: int               # 总轮数
    completion_reason: str          # 完成原因
    duration_seconds: float         # 耗时


class SupervisorAgent:
    """
    Supervisor Agent - 研究主管

    负责：
    1. 规划研究方向
    2. 派发研究任务
    3. 评估研究进展
    4. 决定何时结束

    使用方式：
    ```python
    supervisor = SupervisorAgent(qwen_api_key="...")
    result = supervisor.run("对比 Transformer 和 RNN")
    print(result.state.notes)
    ```
    """

    def __init__(
        self,
        qwen_api_key: Optional[str] = None,
        researcher: Optional[Researcher] = None,
        max_rounds: int = 10,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ):
        """
        初始化 Supervisor

        Args:
            qwen_api_key: 通义千问 API Key
            researcher: Researcher 实例（可选，默认自动创建）
            max_rounds: 最大研究轮数
            progress_callback: 进度回调 (message, progress_ratio)
        """
        self.api_key = qwen_api_key
        self.llm_client = QwenClient(api_key=qwen_api_key) if qwen_api_key else None
        self.researcher = researcher or Researcher(qwen_api_key=qwen_api_key)
        self.max_rounds = max_rounds
        self.progress_callback = progress_callback

    def _report_progress(self, message: str, progress: float):
        """报告进度"""
        if self.progress_callback:
            self.progress_callback(message, progress)
        log.info(f"[Supervisor] {message} ({progress*100:.0f}%)")

    def run(self, query: str, research_brief: str = "") -> SupervisorResult:
        """
        执行研究任务

        Args:
            query: 用户查询
            research_brief: 研究简报（可选）

        Returns:
            SupervisorResult: 运行结果
        """
        start_time = datetime.now()

        # 初始化状态
        state = create_initial_state(query, research_brief)
        state.max_rounds = self.max_rounds

        log.info(f"[Supervisor] 开始研究: {query[:50]}...")
        self._report_progress("正在分析问题...", 0.05)

        # 构建初始消息
        messages = self._build_initial_messages(state)

        # 主循环
        round_count = 0
        consecutive_low_yield = 0  # 连续低产出轮数
        previous_source_count = 0  # 上轮去重后的论文数

        while not state.is_complete and round_count < self.max_rounds:
            round_count += 1
            log.info(f"[Supervisor] === 第 {round_count} 轮 ===")

            progress = 0.1 + (round_count / self.max_rounds) * 0.7
            self._report_progress(f"研究中...（第 {round_count} 轮）", progress)

            # 调用 LLM 获取下一步行动
            response = self._call_llm(messages)

            if not response:
                log.error("[Supervisor] LLM 调用失败")
                state.mark_complete("LLM 调用失败")
                break

            # 解析工具调用
            tool_calls = self._extract_tool_calls(response)

            if not tool_calls:
                # 没有工具调用，可能是直接回复
                log.warning("[Supervisor] 无工具调用，尝试继续")
                messages.append({"role": "assistant", "content": response.get("content", "")})
                messages.append({
                    "role": "user",
                    "content": "请使用工具继续研究，或调用 research_complete 结束研究。"
                })
                continue

            # 处理工具调用
            for tool_call in tool_calls:
                tool_name = tool_call.get("function", {}).get("name", "")
                tool_args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
                tool_id = tool_call.get("id", f"call_{round_count}")

                log.debug(f"[Supervisor] 工具调用: {tool_name}, 参数: {tool_args}")

                # 解析工具
                tool = parse_tool_call(tool_name, tool_args)

                if isinstance(tool, ThinkTool):
                    # 思考工具
                    state.add_thinking(tool.thought, round_number=round_count)
                    log.info(f"[Supervisor] 思考: {tool.thought[:100]}...")

                    # 添加工具响应
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": f"思考已记录。请继续下一步行动。"
                    })

                elif isinstance(tool, ConductResearch):
                    # 派发研究任务
                    log.info(f"[Supervisor] 派发研究: {tool.topic}")
                    self._report_progress(f"研究: {tool.topic[:30]}...", progress + 0.05)

                    # 调用 Researcher
                    research_result, raw_data = self.researcher.research(tool, round_number=round_count)

                    # 更新状态
                    note = ResearchNote(
                        topic=research_result.topic,
                        findings=research_result.findings,
                        key_points=research_result.key_points,
                        sources=research_result.sources,
                        round_number=round_count
                    )
                    state.add_note(note)

                    raw_note = RawNote(
                        topic=raw_data.topic,
                        papers=raw_data.papers,
                        search_keywords=raw_data.keywords,
                        round_number=round_count
                    )
                    state.add_raw_note(raw_note)

                    # 添加工具响应
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": research_result.to_message()
                    })

                    # === P2-1: 信息饱和检测 ===
                    current_source_count = len(state.get_all_sources())
                    new_papers = current_source_count - previous_source_count
                    log.debug(f"[Supervisor] 新增论文: {new_papers} (总计: {current_source_count})")

                    if new_papers <= 1:
                        consecutive_low_yield += 1
                        log.info(f"[Supervisor] 低产出轮次: {consecutive_low_yield}/2")

                        # 连续 2 轮低产出，提示 LLM 考虑结束
                        if consecutive_low_yield >= 2 and round_count >= 3:
                            log.info("[Supervisor] 信息饱和，建议结束研究")
                            messages.append({
                                "role": "user",
                                "content": "注意：连续两轮搜索未发现新的高质量论文，信息可能已饱和。如果你认为研究已经充分，请调用 research_complete 结束研究。"
                            })
                    else:
                        consecutive_low_yield = 0  # 重置计数器

                    previous_source_count = current_source_count

                elif isinstance(tool, ResearchComplete):
                    # 研究完成
                    log.info(f"[Supervisor] 研究完成: {tool.reason}")
                    state.mark_complete(tool.reason)

                    # 添加工具响应
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": f"研究已标记完成。原因: {tool.reason}"
                    })
                    break

                else:
                    log.warning(f"[Supervisor] 未知工具: {tool_name}")

        # 检查是否因达到最大轮数而结束
        if not state.is_complete:
            state.mark_complete(f"达到最大轮数 ({self.max_rounds})")
            log.warning(f"[Supervisor] 达到最大轮数限制")

        # 计算耗时
        duration = (datetime.now() - start_time).total_seconds()

        self._report_progress("研究完成", 0.85)

        return SupervisorResult(
            state=state,
            total_rounds=round_count,
            completion_reason=state.completion_reason,
            duration_seconds=duration
        )

    def _build_initial_messages(self, state: AgentState) -> List[Dict]:
        """构建初始消息"""
        return [
            {"role": "system", "content": SUPERVISOR_SYSTEM_PROMPT},
            {"role": "user", "content": SUPERVISOR_START_PROMPT.format(
                research_brief=state.research_brief
            )}
        ]

    def _call_llm(self, messages: List[Dict]) -> Optional[Dict]:
        """调用 LLM"""
        if not self.llm_client:
            log.error("[Supervisor] LLM 客户端未初始化")
            return None

        try:
            # 使用 httpx 直接调用支持 tools 的 API
            import httpx

            response = httpx.post(
                self.llm_client.API_URL,
                headers={
                    "Authorization": f"Bearer {self.llm_client.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen-plus",  # 使用 plus 模型处理复杂任务
                    "messages": messages,
                    "tools": TOOL_SCHEMAS,
                    "tool_choice": "auto",
                    "max_tokens": 2000,
                    "temperature": 0.3
                },
                timeout=60.0
            )
            response.raise_for_status()

            result = response.json()
            return result.get("choices", [{}])[0].get("message", {})

        except Exception as e:
            log.error(f"[Supervisor] LLM 调用出错: {e}")
            return None

    def _extract_tool_calls(self, response: Dict) -> List[Dict]:
        """提取工具调用"""
        tool_calls = response.get("tool_calls", [])
        if tool_calls:
            return tool_calls

        # 检查是否有 function_call（旧格式）
        function_call = response.get("function_call")
        if function_call:
            return [{
                "id": "call_legacy",
                "type": "function",
                "function": function_call
            }]

        return []


# 测试代码
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    print("=" * 60)
    print("V2 Supervisor Agent 测试")
    print("=" * 60)

    def progress_callback(msg, progress):
        print(f"[进度] {msg} - {progress*100:.0f}%")

    # 创建 Supervisor
    supervisor = SupervisorAgent(
        qwen_api_key=os.getenv("QWEN_API_KEY"),
        max_rounds=5,
        progress_callback=progress_callback
    )

    # 测试查询
    test_query = "对比 Transformer 和 RNN 在自然语言处理中的优劣"

    # 执行研究
    result = supervisor.run(test_query)

    print("\n" + "=" * 60)
    print("研究结果")
    print("=" * 60)
    print(f"总轮数: {result.total_rounds}")
    print(f"完成原因: {result.completion_reason}")
    print(f"耗时: {result.duration_seconds:.1f}秒")

    print("\n--- 研究笔记 ---")
    print(result.state.get_notes_summary())

    print("\n--- 思考历史 ---")
    for i, thought in enumerate(result.state.thinking_history, 1):
        print(f"{i}. {thought[:100]}...")

    print("\n--- 来源论文 ---")
    for src in result.state.get_all_sources()[:5]:
        print(f"  - [{src.get('year', 'N/A')}] {src.get('title', 'Unknown')[:50]}...")
