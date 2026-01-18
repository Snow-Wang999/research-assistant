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

##### 3. 本地论文库功能改进 📋 待实现

> **问题发现**: 2026-01-16 测试时发现当前PDF上传功能存在多处不足

**当前问题：**
- [ ] 标题提取不准确（显示 arXiv ID 而非真正标题）
- [ ] 摘要提取失败（"未能自动提取摘要"）
- [ ] 全文只显示前3000字，无法查看完整内容
- [ ] 切片只有预览，无交互功能

**用户核心需求（P0）：**
- [ ] 全文显示：分页或虚拟滚动加载，而非截断
- [ ] 分块读取 + 一键复制：每个切片有复制按钮
- [ ] 翻译功能：选中切片调用 LLM 翻译成中文
- [ ] 总结功能：一键生成全文摘要/要点提取

**补充功能（P1）：**
- [ ] 目录导航：长论文需要章节跳转（自动解析 Contents）
- [ ] 关键词搜索：在全文中搜索定位
- [ ] 引用生成：一键生成 BibTeX / GB/T 7714 格式

**进阶功能（P2）：**
- [ ] 与 Deep Research 联动：上传的 PDF 可作为研究素材加入分析
- [ ] PDF 原文对照：切片旁边显示对应 PDF 页面截图
- [ ] 批注/高亮：用户可标记重点段落

**论文对话与学习（P1 - 核心差异化功能）：**
> 目标：让用户能与论文"对话"，深度学习和理解论文内容

- [ ] **论文问答对话**：基于上传的PDF进行多轮对话
  - 用户提问 → 检索相关切片 → LLM 生成回答 + 引用来源
  - 支持追问和上下文记忆
- [ ] **观点提取**：自动识别论文中的核心观点/论点
  - 区分：作者主张 vs 引用他人观点 vs 实验结论
  - 按章节组织观点列表
- [ ] **重点总结**：智能提取论文重点
  - 研究问题、方法、主要发现、局限性、未来方向
  - 支持自定义总结角度（如：只看方法部分）
- [ ] **概念解释**：选中术语，LLM 结合上下文解释
- [ ] **学习笔记生成**：基于对话历史自动生成学习笔记

---

### Phase U - 用户评测准备 (v0.4.7) 📋 在 Phase R/S 之后

> **依赖**: Phase R 架构重构、Phase S 搜索增强完成后开始
> **目标**: 让用户能顺利完成任务、能给出有效反馈。不追求美观，追求可用。

#### U1: 进度与状态优化（必须）
- [ ] 研究进度实时显示（当前第几步/共几步）
- [ ] 预估完成时间（基于历史数据）
- [ ] 清晰的"正在做什么"提示（如：正在分解问题、正在搜索论文、正在生成报告）
- [ ] 长时间等待时的友好提示（如：深度研究通常需要2-3分钟）

#### U2: 结果呈现优化（建议）
- [ ] 核心发现摘要置顶（一眼可见的 3-5 句话总结）
- [ ] 报告章节折叠/展开
- [ ] 锚点导航（快速跳转到感兴趣的部分）
- [ ] 论文列表分页或懒加载

#### U3: 引导与说明（建议）
- [ ] 首页使用说明（简短，3-5 句话）
- [ ] 示例问题更突出（按钮样式，不只是文字链接）
- [ ] 输入框 placeholder 更具引导性
- [ ] 错误信息友好化 + 建议下一步

#### U4: 反馈收集（必须）
- [ ] 结果页添加"有用/没用"评分按钮
- [ ] 简单反馈表单入口（可用 Gradio 表单或外链问卷）
- [ ] 记录用户查询（本地日志，用于分析）

**验收标准：**
- 新用户能在无指导下完成一次完整查询
- 等待过程不焦虑（知道在做什么、大概要多久）
- 能收集到用户反馈

**预计工作量：** 0.5-1 天

---

### Phase S - 搜索源增强 (v0.4.6) 📋 在 Phase R 之后

> **依赖**: Phase R 架构重构完成后开始
> **为什么需要？** 当前搜索源单一（arXiv + OpenAlex），全文获取覆盖不足，关键词策略未分层。

#### S1: Web Search 发现层（免费方案）
- [ ] 集成 DuckDuckGo Search（免费、无 API Key）
- [ ] 实现论文链接提取器（从搜索结果提取 arXiv ID / DOI）
- [ ] 关键词分层：Web Search 用自然语言，arXiv 用专业术语
- [ ] 并行搜索策略：arXiv + OpenAlex + Web Search 同时进行

**新增模块：** `src/tools/search/web_search.py`
```python
class WebSearch:
    def search(self, query: str) -> List[PaperLink]:
        # 1. 用 DuckDuckGo 搜索 "{query} research paper arxiv"
        # 2. 提取 arXiv ID / DOI 链接
        # 3. 返回论文链接列表
```

#### S2: 全文获取增强
- [ ] OpenAlex 论文：尝试通过 `open_access.url` 获取 PDF
- [ ] DOI 论文：集成 Unpaywall API 查找免费版本
- [ ] 统一全文获取接口：`get_fulltext(paper) -> Optional[str]`

**新增模块：** `src/tools/pdf/fulltext_resolver.py`
```python
class FulltextResolver:
    def resolve(self, paper: Paper) -> Optional[str]:
        # 1. 如果是 arXiv → 直接下载
        # 2. 如果有 open_access.url → 尝试下载
        # 3. 如果有 DOI → 查询 Unpaywall
        # 4. 返回 PDF 路径或 None
```

#### S3: 搜索策略改进（解决500篇问题）
- [ ] 改用「多轮小批量」策略替代「一次大批量」
- [ ] 每轮搜索 20 篇，LLM 筛选 5 篇高相关
- [ ] 根据上轮发现动态调整关键词
- [ ] Supervisor 决定何时停止（而非固定轮数）

**搜索策略对比：**
```
❌ 旧策略: 一次搜500篇 → LLM筛选
   问题: API超时、噪音多、筛选成本高

✅ 新策略: 多轮小批量 + 智能终止
   第1轮: 搜索20篇 → 筛选5篇
   第2轮: 调整关键词 → 搜索20篇 → 筛选5篇
   ...直到 Supervisor 认为"够了"
```

#### S4: 关键词分层系统
- [ ] QueryAnalyzer 生成两类关键词：
  - `academic_keywords`: 专业术语（给 arXiv/OpenAlex）
  - `discovery_keywords`: 自然语言（给 Web Search）
- [ ] 示例：
  - 用户输入: "大模型在医疗领域的应用"
  - academic: ["LLM healthcare", "clinical NLP", "medical language model"]
  - discovery: ["大模型 医疗 最新研究", "GPT 医院应用 论文"]

**验收标准：**
- Web Search 能发现 arXiv 直接搜不到的热门论文
- 全文获取覆盖率从 ~30%（仅arXiv）提升到 ~60%
- 搜索不再超时，单次请求 ≤ 20篇

---

### Phase R - Deep Research 架构重构 (v0.4.5) ⭐ 关键重构

> **为什么需要重构？** 当前架构存在根本性问题：先定结构后搜索、无反思机制、固定3轮。详见 [架构诊断报告](docs/Deep%20Research架构诊断报告.md) 和 [重构计划](docs/deep_research_refactor_plan.md)

> **优先级：** 架构问题是根本性的，先重构再优化搜索。Phase S 在此之后进行。

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

#### R5: V2 测试问题修复 📋 2026-01-16 评测发现

> **测试查询**: "AI Agent 的研究现状与挑战"
> **结果**: 10轮研究，21篇论文，223秒完成

**P0 - 必须修复（影响基本使用）：**

| # | 问题 | 位置 | 修复方案 |
|---|------|------|----------|
| 1 | 模式显示 Bug | `app.py:226` | V2 返回 `deep_research_v2` 但判断 `== "deep_research"`，改用 `in (...)` |
| 2 | 参考来源不换行 | `orchestrator_v2.py:247` | `"\n".join` 改为 `"\n\n".join` 或用列表格式 |
| 3 | 引用编号不一致 | 报告生成 prompt | 统一论文索引，报告引用 = 参考来源编号 |
| 4 | 论文列表无摘要 | `main.py:302` | V2 清空 `abstract: ""`，应保留前 200 字 |

**P1 - 体验优化：**

- [ ] 合并 arXiv/OpenAlex 两栏为一栏 + `[来源]` 标签
- [ ] 思考过程与研究轮次对应显示（`第N轮思考 → 研究结果`）
- [ ] 思考内容压缩到 50 字或折叠展示
- [ ] 显示搜索统计（"搜索 X 篇 → 筛选 Y 篇"）

**P2 - 功能增强：**

- [ ] V2 全文支持（当前 `use_fulltext: False` 未实现）
- [ ] 智能提前终止（信息饱和检测，避免跑满 10 轮）
- [ ] Markdown / BibTeX 导出

#### R6: UI 强化计划 📋 对标 Gemini/GPT Deep Research

> **目标**: 提升报告展示体验，从"工具感"升级为"产品感"

**Gradio 方案（短期）：**

##### 6.1 添加"全屏查看报告"按钮 + 专用 Tab
> 实现思路：新增 Tab 4 专门展示报告，深度研究完成后可一键跳转

- [ ] 在 `app.py` 添加 Tab 4 "报告查看"
  ```python
  with gr.Tab("报告", id="report_view"):
      report_fullscreen = gr.Markdown(label="研究报告全文")
  ```
- [ ] 深度研究区域添加"📖 全屏查看"按钮
- [ ] 按钮点击后：1) 复制报告内容到 Tab 4  2) 切换到 Tab 4
- [ ] 使用 `tabs.select()` 实现 Tab 切换

##### 6.2 思考过程用 Accordion 折叠
> 实现思路：将思考过程放入可折叠区域，默认收起

- [ ] 修改 `app.py` 报告输出区域，添加 `gr.Accordion`
  ```python
  with gr.Accordion("🧠 思考过程", open=False):
      thinking_output = gr.Markdown()
  ```
- [ ] 修改 `stream_research()` 函数，分离思考过程和报告内容
- [ ] 思考过程默认折叠，报告主体直接展示

##### 6.3 报告区域扩大 + 章节折叠（可选）
- [ ] 调整 Column scale 比例（当前 7:3，可改为 8:2）
- [ ] 报告章节支持折叠/展开（需解析 Markdown 标题）

**React 迁移（长期，可选）：**
- [ ] 后端改为 FastAPI
- [ ] 前端用 React + Tailwind
- [ ] 实现真正的 Modal 弹窗、拖拽、动画效果
- [ ] 预计工作量：3-5 天

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
| M4.5-R | **架构重构（V3标准 Supervisor 循环）** | 📋 待开始 |
| M4.6-S | **搜索源增强（Web Search + 全文获取 + 关键词分层）** | 📋 待开始 |
| M4.7-U | **用户评测准备（进度优化 + 反馈收集）** | 📋 待开始 |
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

# 2. 创建虚拟环境并安装依赖（首次）
uv venv
.venv\Scripts\activate
uv sync

# 3. 运行（使用虚拟环境 Python）
.venv/Scripts/python.exe run.py              # CLI模式
.venv/Scripts/python.exe run.py --web        # Web模式
.venv/Scripts/python.exe run.py --web --share  # Web + 公开链接

# Claude Code 注意：必须使用 .venv/Scripts/python.exe 而非系统 python
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
