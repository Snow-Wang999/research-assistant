下面给你一份**可直接用于 PRD / 架构对齐 / 面试讲解 / Demo 设计**的：

> **《文献综述 Deep Research 产品功能结构图（结构化拆解版）》**

我按 **用户任务流 + 系统模块 + 技术实现 + 产品价值** 四层一起拆，保证你能一眼看懂“怎么做成产品”。

---

# 一、整体定位

**目标任务：**

> 用户输入一个研究主题 → 系统输出一份可溯源、结构化、可继续写论文的文献综述草稿。

---

# 二、用户任务主流程（产品视角）

```
研究主题输入
   ↓
研究范围与约束确认
   ↓
研究路径规划（Deep Research Planner）
   ↓
多源文献检索（RAG）
   ↓
证据融合与聚类
   ↓
综述结构生成
   ↓
段落级引用映射
   ↓
可编辑综述草稿输出
```

---

# 三、产品功能结构图（模块级）

## 1️⃣ 研究输入与约束层（Research Setup Layer）

**功能：**

* 研究主题输入
* 研究范围限定

  * 时间范围
  * 领域子方向
  * 论文类型（survey / method / application）
  * 顶会优先 / 高引用优先
* 输出语言 / 风格选择

**产品价值：**

* 避免综述跑偏
* 为后续 Deep Research 提供边界条件

---

## 2️⃣ Deep Research Planner（核心大脑）

**功能：**

* 自动拆解研究问题为子主题
* 生成研究路径树

示例输出：

```
Topic: AI Agent Evaluation

→ Background & Evolution
→ Agent Architectures
→ Evaluation Benchmarks
→ Metrics
→ Open Challenges
```

**技术点：**

* LLM + 结构化任务拆解 Prompt
* 支持用户编辑路径

---

## 3️⃣ 多源文献检索层（RAG Retrieval Layer）

**数据源：**

* arXiv
* Semantic Scholar
* OpenReview
* GitHub
* 官方博客
* YouTube 技术演讲

**功能：**

* 每个子主题独立检索
* 返回论文 + 元数据
* 支持去重 / 排序 / 质量打分

---

## 4️⃣ 证据聚合与主题聚类层（Evidence Aggregation）

**功能：**

* 相同观点论文聚类
* 方法流派自动分组
* 时间演化排序
* 识别关键代表论文

输出示例：

```
Method Cluster A: Transformer-based Agents
Method Cluster B: Tool-augmented Agents
Method Cluster C: Multi-agent Frameworks
```

---

## 5️⃣ 综述结构生成层（Review Outline Builder）

**功能：**

* 生成综述章节结构
* 每一章对应研究主题路径

示例：

```
1. Introduction
2. Evolution of AI Agents
3. Architecture Taxonomy
4. Evaluation Methods
5. Open Challenges
```

---

## 6️⃣ 段落生成与证据绑定层（Deep Research Writing Engine）

**功能：**

* 每一段文字：

  * 来源于多个证据融合
  * 每个结论绑定引用

输出逻辑：

> 观点 → 多篇论文支持 → 综合表述 → 引用列表

---

## 7️⃣ 引文映射与溯源系统（Citation Mapper）

**功能：**

* 段落级 → 句子级 → 引文映射
* 支持一键跳转原文
* 支持 BibTeX / EndNote / Zotero 导出

---

## 8️⃣ 综述编辑与交互层（Review Editor）

**功能：**

* 结构可折叠
* 段落可重写
* 引文可替换
* 可继续追问某一段

---

## 9️⃣ 输出与导出层

**支持格式：**

* Markdown
* Word
* LaTeX
* PDF

---

# 四、技术架构对齐图（简化）

```
User
 ↓
UI Input
 ↓
Deep Research Planner (LLM)
 ↓
RAG Retriever
 ↓
Evidence Store (Vector DB + Metadata)
 ↓
Cluster Engine
 ↓
Review Structure Builder
 ↓
Writing Engine (LLM)
 ↓
Citation Mapper
 ↓
Editor UI
```

---

# 五、为什么这个结构是 Deep Research 而不是普通 RAG

| 维度 | 普通 RAG | 你的 Deep Research |
| -- | ------ | ---------------- |
| 输入 | 问题     | 研究任务             |
| 检索 | 单轮     | 多子主题并行           |
| 输出 | 答案     | 研究结构             |
| 证据 | 列表     | 聚类融合             |
| 写作 | 单段     | 综述级              |
| 引用 | 附带     | 结构绑定             |

---

# 六、Demo 最小闭环（MVP 推荐）

如果你只做一个 Demo，我建议：

> **Topic → 研究路径 → 子主题检索 → 聚类 → 一章综述 + 引用**

不需要做全流程。

---

# 七、你在面试中可以怎么讲这个结构

一句话：

> 我的产品不是基于问题回答，而是围绕研究任务构建 Deep Research 工作流，通过研究路径规划、证据聚合与结构化写作，帮助用户完成文献综述这一高认知成本任务。

---

# 八、如果你愿意，我可以继续帮你拆：

* 每一层的 Prompt 设计样例
* 多 Agent vs 单 Agent 实现方式
* 数据结构设计（JSON schema）
* 与 Manus / Claude Research / GPT Deep Research 架构对照
* 或者帮你画成一张 PRD 用结构图文字版

你只需要告诉我：
👉 你是更偏向 **产品 PRD**、**技术架构**、还是 **Demo 实现路径**？
