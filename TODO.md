# 科研助手项目进度

> 最后更新: 2026-01-14 (Phase 4 完成)

---

## 产品定位

> **一个面向硕博研究者的 AI Deep Research 助手，帮助你高效完成文献综述、方法对比与研究路径构建，并为每个结论提供可验证引用来源。**

### 核心认知

| 错误定位 | 正确定位 |
|----------|----------|
| 更聪明的搜索工具 | **更像研究助理的认知系统** |
| 帮用户找论文 | **帮用户完成研究任务** |
| 引用查找工具 | **结构化研究报告生成器** |

### 产品主线判断

| 项目 | 是否核心 | 说明 |
|------|----------|------|
| Deep Research | ✅ 核心 | 认知组织与研究路径生成引擎 |
| 文献综述 | ✅ 核心 | P0 场景 |
| 方法对比 | ✅ 核心 | P0 场景 |
| 选题调研 | ✅ 次核心 | P1 场景，产品成熟后扩展 |
| 引文查找 | ❌ 支撑能力 | Deep Research 输出的可信度系统，不是卖点 |
| 跟踪前沿 | ❌ 可插件化 | 不作为主线 |
| 论文复现 | ❌ 不适合主线 | 不做 |

---

## 已完成 ✅

### Phase 1 - MVP基础架构 (v0.1.0)
- [x] 项目初始化（目录结构、配置文件）
- [x] 意图路由器 (Intent Router) - 区分简单/深度查询
- [x] Semantic Scholar 论文搜索集成
- [x] arXiv 论文搜索集成
- [x] 统一搜索器（并行搜索 + 结果合并去重）
- [x] 语义压缩器基础版（简单规则，无LLM）
- [x] CLI 命令行界面
- [x] Gradio Web 界面
- [x] 启动脚本 (run.py / run.bat)
- [x] 单元测试框架 + 评估用例
- [x] 架构文档

### Phase 2 - 智能分析 (v0.2.0)
- [x] QueryAnalyzer 智能查询分析（多关键词生成）
- [x] ReadingGuide 阅读导航（入门/核心/最新论文推荐）
- [x] AbstractSummarizer 摘要中文总结
- [x] OpenAlex 搜索集成（替代 Semantic Scholar）
- [x] 搜索结果综合排序（相关性 + 时间 + 引用）
- [x] 论文分类功能

### Phase 3 - 深度研究 (v0.3.0) ✅
- [x] SubQuestionDecomposer 子问题分解器
- [x] ResearchAgent 研究员 Agent（并行搜索 + LLM压缩）
- [x] ReportGenerator 研究报告生成器（带引用标注）
- [x] DeepResearchOrchestrator 深度研究协调器（超时控制）
- [x] 整合到主入口和 UI
- [x] 流式输出 + 停止按钮
- [x] 各阶段耗时显示
- [x] 论文列表独立编号说明

---

## 进行中 🚧

### Phase 4 - PDF 全文获取 (v0.4.0) ⭐ 当前重点

> **为什么跳过 v0.3.1？** 当前 Deep Research 只有摘要数据，优化天花板有限。获取全文后才能真正提升能力。

#### arXiv PDF 自动获取（Week 1）✅
- [x] arXiv 论文自动下载 PDF（通过 arxiv_id）
- [x] PDF 解析（PyMuPDF + 双栏处理）
- [x] 段落/句子切分与位置保留
- [ ] 与搜索结果关联展示

**新增模块：** `src/tools/pdf/`
- `arxiv_downloader.py` - arXiv PDF 下载器
- `pdf_parser.py` - PDF 解析器（PyMuPDF）
- `chunker.py` - 文档切片器
- `paper_processor.py` - 论文处理器（集成流程）

#### Deep Research 升级（Week 2）✅
- [x] 论文筛选器 - LLM 基于摘要筛选相关论文
- [x] 全文研究员 Agent - 使用 PDF 全文进行研究
- [x] Deep Research 支持全文模式
- [x] UI 重构 - Tab + Sidebar 架构

**新增模块：**
- `src/tools/paper_screener.py` - 论文筛选器
- `src/agents/deep_research/fulltext_research_agent.py` - 全文研究员

**UI 重构（v0.4.0）：**
- `ui/app.py` - Tab + Sidebar 架构重构
  - Tab 1: 搜索（快速模式）
  - Tab 2: 深度研究（含全文研究选项）
  - Tab 3: 论文库（占位）
  - 统一侧边栏：论文详情展示

**流程升级：** 搜索 → 筛选 → 下载 PDF → 全文研究 → 报告生成

---

#### Phase 4 收尾 - 已完成功能 ✅

##### 1. 报告句级引用 ✅
> 报告现在支持句级证据追溯，在全文研究模式下会显示支持句

- [x] 增强 `fulltext_research_agent.py` 的 `_build_sources()` 方法
- [x] 添加 `SupportingEvidence` 数据类保存句子位置信息
- [x] 修改 COMPRESS_PROMPT 要求 LLM 返回 supporting_sentences
- [x] 报告中添加 "📌 支持证据" 章节，显示关键支持句和页码
- [x] 参考来源显示 📄全文 标记和 arXiv 链接

**实现的功能：**
- LLM 返回具体支持句，包含来源论文编号 [P1][P2]
- 句子与 PDF 位置信息自动匹配
- 报告末尾按论文分组显示支持证据

##### 2. 用户 PDF 上传 ✅
> 用户可以在 Tab 3 论文库中上传本地 PDF 进行分析

- [x] UI Tab 3 添加 PDF 上传组件
- [x] 扩展 `PaperProcessor.process_local_pdf()` 支持本地 PDF
- [x] 显示解析结果：标题、页数、全文长度、切片数
- [x] 显示摘要（自动提取）
- [x] 显示全文预览（前3000字）
- [x] 显示切片统计和预览

---

### Phase R - Deep Research 架构重构 (v0.4.5) ⭐ 关键重构

> **为什么需要重构？** 当前架构存在根本性问题：先定结构后搜索、无反思机制、固定3轮。详见 [架构诊断报告](docs/Deep%20Research架构诊断报告.md) 和 [重构计划](docs/deep_research_refactor_plan.md)

#### R1: Supervisor 循环（核心）
- [ ] 创建 `v2/` 目录，保留现有代码
- [ ] 移除 SubQuestionDecomposer，改为 Research Brief（开放式主题）
- [ ] 实现 Supervisor 动态决策循环（while not complete）
- [ ] 添加 think_tool 显式反思工具
- [ ] 实现 ResearchComplete 终止条件（LLM 决定何时停止）

#### R2: Subagent as Tool
- [ ] Researcher 作为 ConductResearch 工具暴露给 Supervisor
- [ ] 返回 CompressedResearch 而非完整 Paper 列表
- [ ] 子 Agent 独立上下文隔离

#### R3: 状态管理
- [ ] 实现 override_reducer（支持覆盖/追加两种模式）
- [ ] raw_notes（原始数据卸载）/ notes（压缩结果检索）分离
- [ ] AgentState 统一状态管理

#### R4: 质量提升（可选）
- [ ] CitationAgent 引用验证
- [ ] 动态报告结构（基于发现组织，而非预设章节）

**新增文件结构：**
```
src/agents/deep_research/v2/
├── supervisor.py           # Supervisor Agent 主循环
├── researcher.py           # Researcher Subagent
├── state.py                # AgentState + reducers
├── tools.py                # think_tool, ConductResearch, ResearchComplete
├── prompts.py              # Prompt 模板
└── orchestrator_v2.py      # V2 协调器入口
```

**验收标准：**
- 简单问题 2-3 轮，复杂问题 5-10 轮（动态）
- 报告篇幅显著增加
- think_tool 思考过程可见

---

## 暂缓 ⏸️ (原 v0.3.1)

> 基于摘要的优化天花板有限，等 v0.4.0 全文获取后再评估是否需要

### 原 Phase 3.1 内容（后置）
- [ ] 评测体系建设（v0.4.0 后建立更有意义）
- [ ] 搜索质量优化
- [ ] 用户体验优化

---

## 待开始 📋

---

### Phase 5 - 证据追溯与聚类 (v0.5.0) - 学术可信分水岭

> 这是产品从"AI写作工具"升级为"AI研究系统"的关键能力

#### 句级证据追溯（Evidence Traceability）
- [ ] PDF 全文段落/句子切分
- [ ] 结论 → 支持句 embedding 匹配
- [ ] Entailment 验证（该句是否真实支持结论）
- [ ] 一键跳转原文定位

#### 证据聚类层（Evidence Aggregation）
- [ ] 相同观点论文自动聚类
- [ ] 方法流派分组（如：Transformer-based / Tool-augmented）
- [ ] 时间演化排序
- [ ] 代表论文识别

#### 引文导出增强
- [ ] BibTeX 导出
- [ ] Zotero 集成
- [ ] EndNote 格式支持

---

## 暂缓 ⏸️

> 根据"核心算法先行、用户反馈驱动"原则，以下功能暂缓

### Phase 6 - 高级功能（需求验证后再开始）
- [ ] 多Agent协作架构
- [ ] 知识图谱构建
- [ ] MCP Server集成
- [ ] 对话记忆管理

### Phase 7 - 工程化（产品稳定后再开始）
- [ ] CI/CD配置
- [ ] Docker部署
- [ ] API文档（FastAPI）

---

## 里程碑

| 里程碑 | 目标 | 状态 |
|--------|------|------|
| M1 | MVP可运行 | ✅ v0.1.0 完成 |
| M2 | 智能分析+阅读导航 | ✅ v0.2.0 完成 |
| M3 | Deep Research完整实现 | ✅ v0.3.0 完成 |
| M4 | PDF 全文获取 + 句级引用 + PDF上传 | ✅ **v0.4.0 完成** |
| M4.5 | **架构重构（V3标准）** | 📋 待开始 |
| M5 | 证据追溯与聚类（学术可信分水岭） | 📋 待开始 |
| M6 | 生产部署 | ⏸️ 暂缓 |

---

## 优先级原则

基于产品定位「认知重建系统」而非「搜索工具」：

1. **Deep Research 为主线** - 所有功能围绕「帮用户完成研究任务」展开
2. **文献综述 + 方法对比为 P0** - 这是产品护城河最强的场景
3. **引文作为可信度系统** - 不作为卖点，但每个结论都要有可验证来源
4. **架构问题优先解决** - 功能优化建立在正确架构之上，V3 架构重构是关键
5. **渐进式重构** - 保留现有代码，v2/ 目录实现新架构，对比效果后迁移
6. **收集反馈** - 自己使用+找1-2同学试用

---

## 快速启动

```bash
# 1. 进入项目目录
cd D:\HandDeepResearch_AI\research-assistant

# 2. 创建虚拟环境并安装依赖
uv venv
.venv\Scripts\activate
uv sync

# 3. 运行
python run.py              # CLI模式
python run.py --web        # Web模式
python run.py --web --share  # Web + 公开链接
```

## 项目结构

```
research-assistant/
├── run.py                 # 启动脚本
├── run.bat                # Windows启动脚本
├── src/
│   ├── main.py            # 主入口
│   ├── agents/
│   │   ├── intent_router.py
│   │   └── deep_research/     # v0.3.0 新增
│   │       ├── decomposer.py      # 子问题分解
│   │       ├── research_agent.py  # 研究员Agent
│   │       ├── report_generator.py # 报告生成
│   │       └── orchestrator.py    # 协调器
│   └── tools/
│       ├── search/
│       │   ├── arxiv_search.py
│       │   ├── openalex_search.py
│       │   └── unified_search.py
│       ├── query_analyzer.py
│       ├── reading_guide.py
│       └── abstract_summarizer.py
└── ui/
    └── app.py             # Gradio界面
```

## v0.3.0 Deep Research 架构（待重构）

> ⚠️ **已知问题**: 当前架构存在"先定结构后搜索"、"无反思机制"、"固定3轮"等问题，将在 Phase R 重构为 V3 架构。详见 [重构计划](docs/deep_research_refactor_plan.md)

```
用户复杂查询
      │
      ▼
┌──────────────────────────┐
│  SubQuestionDecomposer   │  ← ❌ 预设3个子问题（将改为 Research Brief）
│  "对比 A 和 B"            │
│   → ["A核心概念", "B核心概念", "A与B对比"]
└──────────────────────────┘
      │
      ▼  (并行执行)
┌──────────────────────────┐
│    ResearchAgent × N     │  ← ❌ 固定3轮，无反思（将改为 Supervisor 循环）
│  ├─ 子问题1 → 搜索+压缩   │
│  ├─ 子问题2 → 搜索+压缩   │
│  └─ 子问题3 → 搜索+压缩   │
└──────────────────────────┘
      │
      ▼
┌──────────────────────────┐
│    ReportGenerator       │  ← 汇总生成结构化报告
│  - 概述                   │
│  - 各子问题分析           │
│  - 综合结论               │
└──────────────────────────┘
```
