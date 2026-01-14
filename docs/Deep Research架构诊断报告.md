# 🔴 Deep Research 架构诊断报告
# 1. 核心问题总结
你的 Deep Research 实现确实偏离了 V3 架构的核心设计，导致：

❌ 结构僵化（先定结构后搜索）
❌ 深度不足（固定 3 轮，无反思机制）
❌ 篇幅短（无法应对复杂查询）
# 2. 六大架构差距
差距 1：❌ 先定结构后搜索（最严重）
维度	Open Deep Research V3	当前实现
问题分解时机	搜索过程中动态发现	搜索前预设 3 个子问题
结构来源	Research Brief（开放式主题）	SubQuestionDecomposer（固定结构）
报告结构	搜索发现的自然呈现	预设章节拼接
你的代码：


# decomposer.py:107 - 先定结构
def decompose(self, query: str) -> DecompositionResult:
    # 分解为 3 个固定子问题
    sub_questions = [...]  # ❌ 预设结构
    return DecompositionResult(sub_questions=sub_questions)

# orchestrator.py:141 - 然后按固定结构搜索
decomposition = self.decomposer.decompose(query)
research_results = self.research_runner.run(
    sub_questions=decomposition.sub_questions  # ❌ 固定路线
)
V3 标准：


# write_research_brief - 只生成开放式 Brief
response = ResearchQuestion(research_brief="探索 Transformer vs RNN")  # ✓ 不预设结构

# supervisor - 动态决定研究方向
supervisor → think_tool("需要对比什么？") 
          → ConductResearch("Transformer 自注意力机制")
          → 评估 → 决定是否继续
          → ConductResearch("RNN 序列建模能力")  # ✓ 动态扩展
差距 2：❌ 无反思机制
维度	V3 标准	当前实现
反思工具	think_tool（显式思考）	无
动态决策	Supervisor 循环评估	一次性执行
终止条件	ResearchComplete（LLM 判断）	固定 3 轮
你的代码：


# orchestrator.py:154-165 - 一条路走到黑
research_results = self.research_runner.run(
    sub_questions=decomposition.sub_questions,  # ❌ 固定 3 个
    limit_per_question=self.config.papers_per_question
)
# 没有"评估 → 继续/停止"的循环
V3 标准：


# supervisor 循环
while True:
    # 反思：需要继续吗？
    response = supervisor_model.invoke([
        SystemMessage(lead_researcher_prompt),
        *supervisor_messages
    ])
    
    if response.tool_calls:
        if "ConductResearch" in response.tool_calls:
            # 动态派发更多研究
            researcher_result = run_researcher(...)
            supervisor_messages.append(researcher_result)
        elif "ResearchComplete" in response.tool_calls:
            break  # ✓ LLM 决定何时停止
差距 3：❌ Subagent 不是工具调用
维度	V3 标准	当前实现
协作机制	Subagent as Tool（ConductResearch）	ThreadPoolExecutor 并行
上下文隔离	子 Agent 独立 MessagesState	无隔离
返回值	compressed_research（可控）	ResearchResult（完整对象）
你的代码：


# research_agent.py:252 - 使用线程池并行
class ParallelResearchRunner:
    def run(self, sub_questions, limit_per_question):
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(agent.research, sq, limit_per_question)
                for sq in sub_questions  # ❌ 静态并行
            ]
        return [f.result() for f in as_completed(futures)]
V3 标准：


# supervisor.py:200 - 工具调用
supervisor_model = model.bind_tools([
    think_tool,  
    ConductResearch,  # ✓ 子 Agent 作为工具
    ResearchComplete
])

# researcher 作为子图
researcher_graph = StateGraph(ResearcherState)
researcher_graph.add_node("researcher", researcher)
researcher_graph.add_node("compress_research", compress_research)  # ✓ 自动压缩
差距 4：❌ 上下文管理不完善
维度	V3 标准	当前实现
卸载	raw_notes 外部存储	❌ 无
减少	LLM 语义压缩	✅ 有（但不自动）
隔离	Subagent 独立上下文	❌ 无
检索	notes 按需访问	❌ 无
你的代码：


# 只有压缩，无卸载/隔离/检索
compressed_findings: str  # ✓ 有压缩
# 但 Supervisor 直接接收所有 ResearchResult 对象
V3 标准：


class AgentState(MessagesState):
    supervisor_messages: Annotated[list, override_reducer]  # ✓ 隔离
    raw_notes: Annotated[list, override_reducer]  # ✓ 卸载
    notes: Annotated[list, override_reducer]  # ✓ 检索
差距 5：❌ 无 override_reducer
维度	V3 标准	当前实现
状态更新	灵活模式（可覆盖/追加）	简单 dataclass
初始化	覆盖模式	追加模式
运行时	追加模式	追加模���
你的代码：


# orchestrator.py:34-54 - 简单 dataclass
@dataclass
class DeepResearchOutput:
    query: str
    decomposition: DecompositionResult
    research_results: list  # ❌ 无 reducer
    report: ResearchReport
V3 标准：


def override_reducer(current_value, new_value):
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)  # ✓ 可覆盖
    else:
        return operator.add(current_value, new_value)  # ✓ 可追加

class AgentState(MessagesState):
    supervisor_messages: Annotated[list, override_reducer]  # ✓ 灵活模式
差距 6：❌ 篇幅短、深度不足
维度	V3 标准	当前实现
研究轮数	动态（直到 Supervisor 满意）	固定 3 轮
论文总数	根据需要扩展	30×3 = 90 篇（固定）
质量保障	Supervisor 反思 + CitationAgent	无
影响：

简单问题：3 轮可能够
复杂问题（对比分析、综述）：远远不够
# 3. 为什么篇幅短？
你的感觉是对的。对比标准实现：

场景	V3 标准	当前实现
简单问题	2-3 轮研究 → 报告	3 轮（固定）
复杂问题	5-10 轮研究 → 报告	3 轮（不够）
对比分析	动态扩展：对比对象 + 性能评测 + 应用场景 + ...	仅 3 个子问题
根本原因：

无反思循环 → 无法动态扩展
先定结构 → 错过重要角度
固定轮数 → 深度不足
# 4. 重构方案（按优先级）
🔴 P0 - 架构级重构（必须）
移除 SubQuestionDecomposer

改为生成 Research Brief（开放式主题描述）
不预设子问题
引入 Supervisor 循环


class SupervisorAgent:
    def plan_and_research(self, research_brief):
        while not self.is_complete():
            # 反思：下一步研究什么？
            next_action = self.think()
            
            if next_action == "conduct_research":
                result = self.call_researcher(topic)
                self.supervisor_notes.append(result.compressed_research)
            elif next_action == "complete":
                break
        
        return self.generate_final_report()
实现 Subagent as Tool

Researcher 作为工具暴露给 Supervisor
返回 compressed_research 而非完整对象
🟡 P1 - 上下文管理（重要）
实现 override_reducer

支持灵活的状态更新
引入 raw_notes / notes 机制

卸载：详细内容存 raw_notes
检索：Supervisor 只看 notes
🟢 P2 - 质量提升（推荐）
添加 think_tool

Supervisor 显式思考工具
引入 CitationAgent

专门核对引用准确性
# 5. 参考实现路径
路径 A：渐进式重构（推荐）
保留现有代码
创建 v2/ 目录，实现 V3 架构
对比效果，逐步迁移
路径 B：基于 DeepAgents 框架
直接使用 LangChain DeepAgents
添加 20% 定制（论文搜索工具）
专注于差异化功能（本地 PDF 库）
# 6. 立即行动建议
不建议修修补补，因为问题是架构级的。推荐：

短期：在 docs/ 创建 deep_research_refactor_plan.md，详细设计 V3 架构
中期：实现 Supervisor 循环 + Subagent as Tool
长期：专注差异化（本地 PDF 库、句级引用追溯）
你希望我：

创建详细的重构计划文档？
直接开始实现 V3 架构（新目录）？
先修复当前实现的紧急问题（权宜之计）？

我的命令：创建详细的重构计划文档
claude code：
用户要求创建详细的重构计划文档。根据我之前的诊断分析，我需要创建一份全面的重构计划文档，包括：

当前问题总结
目标架构（V3 标准）
重构路线图
具体实现步骤
风险和注意事项
让我创建这份文档。