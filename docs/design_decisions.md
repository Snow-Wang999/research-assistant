# 设计决策记录 (ADR)

> 记录项目中的关键技术决策，帮助新成员快速理解"为什么这样做"

---

## ADR-001: 采用V3架构（Subagent as Tool）

**日期**: 2025-01-11
**状态**: 已采纳

### 背景
Deep Research类应用面临Context爆炸问题：多轮搜索产生大量文本，导致Token消耗剧增。

### 决策
采用Open Deep Research的V3架构：
1. **Subagent as Tool**: 子Agent作为工具被调用，隔离上下文
2. **LLM语义压缩**: 搜索结果先压缩再返回主Agent
3. **Search-first-then-structure**: 先广泛搜索，再结构化整理

### 后果
- ✅ Token消耗可控
- ✅ 支持更多轮搜索迭代
- ⚠️ 架构复杂度增加

---

## ADR-002: 意图路由决策框架

**日期**: 2025-01-11
**状态**: 已采纳

### 背景
用户查询有简单和复杂之分，不同类型需要不同处理策略。

### 决策
实现IntentRouter，基于规则路由：
- **Simple模式**: 简单事实查询 → 快速RAG检索
- **Deep Research模式**: 复杂分析查询 → 多轮深度搜索

### 路由规则
```
简单关键词: 是什么、定义、作者是谁 → Simple
复杂关键词: 对比、比较、综述、趋势 → Deep Research
默认: 查询长度 > 30字符 → Deep Research
```

### 后果
- ✅ 简单查询响应快
- ✅ 复杂查询结果全面
- ⚠️ 规则可能不够智能（后续可用LLM替换）

---

## ADR-003: 统一搜索器设计

**日期**: 2025-01-11
**状态**: 已采纳

### 背景
需要整合多个论文搜索源（arXiv、Semantic Scholar等）。

### 决策
创建UnifiedSearch统一搜索器：
- 并行调用多个搜索源
- 结果合并去重
- 按引用数排序

### 接口设计
```python
class UnifiedSearch:
    def search(query, limit, sources, parallel) -> SearchResult
    def search_arxiv_only(query, limit) -> List[Paper]
    def search_semantic_scholar_only(query, limit) -> List[Paper]
```

### 后果
- ✅ 统一接口，易于扩展新搜索源
- ✅ 并行搜索提升速度
- ⚠️ 需要处理不同源的数据格式差异

---

## ADR-004: 本地论文库（Phase 2）

**日期**: 2025-01-11
**状态**: 待实现

### 背景
用户希望管理自己的论文收藏，并与在线搜索结合。

### 决策（规划）
使用Claude多模态能力读取本地PDF：
1. 用户指定论文文件夹路径
2. Claude解析PDF内容
3. 建立本地索引（向量化）
4. 搜索时同时查本地+在线

### 差异化价值
这是竞品（Perplexity、Elicit）不具备的功能。

---

## ADR-005: 技术栈选择

**日期**: 2025-01-11
**状态**: 已采纳

| 组件 | 选择 | 理由 |
|------|------|------|
| Web框架 | Gradio | 快速原型，科研友好 |
| HTTP客户端 | httpx | 异步支持，错误处理好 |
| 论文搜索 | Semantic Scholar + arXiv | 免费API，学术覆盖广 |
| 包管理 | uv | 速度快，兼容pip |
| 向量数据库 | Chroma（Phase 2） | 轻量级，本地部署 |
| LLM调用 | LiteLLM（Phase 2） | 统一多家模型API |

---

## 决策模板

```markdown
## ADR-XXX: [标题]

**日期**: YYYY-MM-DD
**状态**: 待讨论 / 已采纳 / 已废弃

### 背景
[描述问题和上下文]

### 决策
[描述采取的方案]

### 后果
- ✅ 好处
- ⚠️ 代价/风险
```
