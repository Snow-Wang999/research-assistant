# Deep Research 架构重构计划

> 基于 Open Deep Research V3 架构标准
> 创建日期: 2026-01-14

---

## 1. 当前问题总结

| 问题 | 严重程度 | 影响 |
|------|----------|------|
| 先定结构后搜索 | 🔴 P0 | 结构僵化，错过重要研究角度 |
| 无反思机制 | 🔴 P0 | 固定3轮，无法动态扩展 |
| Subagent 非工具调用 | 🟡 P1 | 上下文无隔离，不可控 |
| 无状态管理机制 | 🟡 P1 | 无法灵活更新状态 |
| 上下文管理不完善 | 🟢 P2 | Token浪费 |

---

## 2. 目标架构 (V3 标准)

### 核心改变

```
当前架构 (v0.3.0)                    目标架构 (V3)
==================                   ==================

1. SubQuestionDecomposer             1. Research Brief (开放式主题)
   预设3个子问题                          不预设结构

2. 固定3轮并行搜索                    2. Supervisor循环
   无反思                                 动态决策 + think_tool

3. ThreadPoolExecutor                3. Subagent as Tool
   静态并行                               ConductResearch 工具调用

4. 简单dataclass                     4. AgentState + override_reducer
   无状态管理                             灵活状态管理
```

### 目标流程

```
用户查询
    │
    ▼
┌─────────────────────┐
│  Research Brief     │  ← 生成开放式研究主题，不预设结构
│  "探索 X vs Y"      │
└─────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│              Supervisor 循环                 │
│  ┌─────────────────────────────────────┐    │
│  │ while not complete:                  │    │
│  │   1. think_tool() - 反思下一步      │    │
│  │   2. ConductResearch() - 派发研究   │    │
│  │   3. 评估结果 - 是否继续            │    │
│  │   4. ResearchComplete() - 结束      │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Report Generator   │  ← 基于动态发现生成报告
└─────────────────────┘
```

---

## 3. 重构方案

### 方案选择：渐进式重构 (推荐)

| 方案 | 优点 | 缺点 |
|------|------|------|
| **A. 渐进式重构** ✅ | 风险低，可对比效果 | 代码暂时并存 |
| B. 全面重写 | 代码干净 | 风险高，周期长 |
| C. 引入 LangGraph | 架构成熟 | 学习成本，依赖重 |

**决定**: 创建 `v2/` 目录实现新架构，与现有代码并存。

---

## 4. 实现步骤

### Phase R1: Supervisor 循环 (核心)

**目标**: 实现动态研究循环，替代固定3轮

```
新建文件:
src/agents/deep_research/v2/
├── supervisor.py          # Supervisor Agent
├── researcher.py          # Researcher (Subagent as Tool)
├── state.py               # AgentState + override_reducer
└── tools.py               # think_tool, ConductResearch, ResearchComplete
```

**核心代码结构**:

```python
# supervisor.py
class SupervisorAgent:
    def __init__(self, model, tools):
        self.model = model
        self.tools = [think_tool, ConductResearch, ResearchComplete]

    def run(self, research_brief: str) -> SupervisorResult:
        messages = [SystemMessage(LEAD_RESEARCHER_PROMPT)]

        while True:
            response = self.model.invoke(messages)

            if "ConductResearch" in response.tool_calls:
                # 动态派发研究任务
                result = self._run_researcher(response.tool_calls)
                messages.append(result.compressed_research)

            elif "ResearchComplete" in response.tool_calls:
                # LLM决定完成
                break

            elif "think" in response.tool_calls:
                # 显式反思
                messages.append(response.thinking)

        return SupervisorResult(notes=self.notes)
```

**验收标准**:
- [ ] Supervisor 可以动态决定研究轮数
- [ ] 简单问题 2-3 轮，复杂问题 5-10 轮
- [ ] think_tool 输出可见

### Phase R2: Subagent as Tool

**目标**: Researcher 作为工具暴露，返回压缩结果

```python
# tools.py
class ConductResearch(BaseModel):
    """派发研究任务给 Researcher"""
    topic: str = Field(description="具体研究主题")
    search_strategy: str = Field(description="搜索策略: broad/focused")

# researcher.py
class Researcher:
    def research(self, topic: str) -> CompressedResearch:
        # 搜索 → 筛选 → 压缩
        papers = self.search(topic)
        filtered = self.screen(papers)
        compressed = self.compress(filtered)

        # 原始数据存到 raw_notes (外部存储)
        self.raw_notes.append(papers)

        # 只返回压缩结果
        return CompressedResearch(summary=compressed, sources=filtered[:5])
```

**验收标准**:
- [ ] Researcher 作为 Tool 被 Supervisor 调用
- [ ] 返回 CompressedResearch 而非完整 Paper 列表
- [ ] raw_notes 与 notes 分离

### Phase R3: 状态管理

**目标**: 实现灵活的状态更新机制

```python
# state.py
def override_reducer(current, new):
    """支持覆盖或追加"""
    if isinstance(new, dict) and new.get("type") == "override":
        return new.get("value")
    return current + new  # 默认追加

@dataclass
class AgentState:
    messages: List[Message]
    supervisor_messages: List[Message]  # 隔离
    raw_notes: List[Any]                 # 卸载
    notes: List[str]                     # 检索
```

**验收标准**:
- [ ] 支持状态覆盖和追加两种模式
- [ ] Supervisor 只访问 notes，不访问 raw_notes

### Phase R4: 质量提升 (可选)

- [ ] CitationAgent - 验证引用准确性
- [ ] 报告结构优化 - 基于发现动态组织

---

## 5. 与当前计划的整合

### 建议的优先级调整

```
当前 TODO.md:
Phase 4 (PDF全文) → Phase 5 (证据追溯)

建议调整为:
Phase 4 (PDF全文) → Phase R (架构重构) → Phase 5 (证据追溯)
                    ↑
                 新增：2周
```

**理由**:
1. 架构问题是根本性的，越早修复成本越低
2. PDF 全文功能可以在新架构上更好发挥
3. 证据追溯依赖于更灵活的上下文管理

### 时间建议

| 阶段 | 内容 | 依赖 |
|------|------|------|
| Phase 4 收尾 | 完成 PDF 句级引用、用户上传 | 无 |
| Phase R1 | Supervisor 循环 | 无 |
| Phase R2 | Subagent as Tool | R1 |
| Phase R3 | 状态管理 | R2 |
| Phase 5 | 证据追溯 | R1-R3 |

---

## 6. 文件变更清单

### 新增

```
src/agents/deep_research/v2/
├── __init__.py
├── supervisor.py           # Supervisor Agent 主循环
├── researcher.py           # Researcher Subagent
├── state.py                # AgentState + reducers
├── tools.py                # think_tool, ConductResearch, ResearchComplete
├── prompts.py              # Prompt 模板
└── orchestrator_v2.py      # V2 协调器入口
```

### 保留 (暂不修改)

```
src/agents/deep_research/
├── decomposer.py           # 保留，V2完成后废弃
├── research_agent.py       # 保留，V2完成后废弃
├── report_generator.py     # 复用
└── orchestrator.py         # 保留，V2完成后废弃
```

### 修改

```
src/main.py                 # 添加 V2 入口开关
ui/app.py                   # 添加 V2 模式选项 (可选)
```

---

## 7. 风险与注意事项

| 风险 | 应对措施 |
|------|----------|
| V2 开发期间 V1 不可用 | 保持 V1 完整，V2 独立目录 |
| LLM 调用次数增加 | 监控 Token 消耗，设置上限 |
| Supervisor 死循环 | 设置最大轮数 (max_iterations=15) |
| 效果不如预期 | 保留 A/B 对比能力 |

---

## 8. 验收标准

### 最小验收

- [ ] V2 可以完成简单查询 (2-3 轮)
- [ ] V2 可以完成复杂查询 (5+ 轮)
- [ ] 报告篇幅显著增加
- [ ] think_tool 思考过程可见

### 完整验收

- [ ] V2 效果优于 V1 (人工评估)
- [ ] Token 消耗可控 (增加 < 50%)
- [ ] 支持全文模式
- [ ] 证据追溯可用

---

## 9. 下一步行动

1. **立即**: 更新 TODO.md，加入架构重构阶段
2. **本周**: 完成 Phase 4 剩余工作 (句级引用、用户上传)
3. **下周**: 开始 Phase R1 (Supervisor 循环)

---

## 附录: V3 核心 Prompt 参考

### Lead Researcher Prompt

```
You are a senior research lead coordinating a research project.

Your tools:
- think: Explicitly reason about the research direction
- ConductResearch: Delegate research to a specialist
- ResearchComplete: Signal that research is complete

Process:
1. Start with think() to plan the research approach
2. Use ConductResearch() to gather information on specific topics
3. After each result, think() about what's missing
4. Continue until you have comprehensive coverage
5. Call ResearchComplete() when done

Remember:
- Simple topics need 2-3 research rounds
- Complex comparisons need 5-10 rounds
- Always think before conducting research
```
