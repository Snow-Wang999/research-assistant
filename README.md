# Research Assistant

科研助手 Agent - 自动搜索论文、分析内容、生成带引用的研究报告

## 功能特点

- 🔍 **智能搜索**：支持 Semantic Scholar、arXiv 多源搜索
- 🤖 **意图路由**：自动判断使用 RAG 还是 Deep Research 模式
- 📚 **本地论文库**：读取和分析用户本地 PDF 论文（开发中）
- 📝 **带引用报告**：生成可溯源的研究报告

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 ANTHROPIC_API_KEY

# 2. 安装依赖
uv sync

# 3. 运行
python src/main.py
```

## 架构

```
用户查询
    ↓
┌─────────────────┐
│   意图路由       │  ← 判断简单/复杂查询
└────────┬────────┘
         ↓
    ┌────┴────┐
    ↓         ↓
┌───────┐ ┌──────────┐
│ RAG   │ │ Deep     │
│ 模式  │ │ Research │
└───────┘ └──────────┘
    ↓         ↓
    └────┬────┘
         ↓
    研究报告（带引用）
```

## 团队分工

| 模块 | 职责 | 负责人 |
|------|------|--------|
| `src/agents/` | Agent 编排、意图路由 | A |
| `src/tools/` | 搜索工具、本地论文 | B |
| `src/rag/` | 解析、检索、压缩 | B |
| `ui/` + `tests/` | 界面、评测 | C |

## 开发进度

- [x] Week 1: 基础搜索 + 意图路由
- [ ] Week 2: Subagent 架构 + 报告生成
- [ ] Week 3: 本地论文库 + UI

## License

MIT
