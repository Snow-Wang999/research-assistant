# 开发指南

> 新成员入门和日常开发参考

---

## 快速开始

```bash
# 1. 克隆项目
git clone <repo-url>
cd research-assistant

# 2. 环境设置
uv venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

# 3. 安装依赖
uv sync

# 4. 运行
python run.py --web
```

---

## 项目结构

```
research-assistant/
├── run.py                 # 统一启动脚本
├── run.bat                # Windows快捷启动
├── pyproject.toml         # 依赖配置
├── CLAUDE.md              # Claude Code指引
├── TODO.md                # 进度追踪
│
├── src/                   # 源代码
│   ├── main.py            # 主入口
│   ├── agents/            # Agent模块
│   │   └── intent_router.py
│   ├── tools/             # 工具模块
│   │   └── search/
│   │       ├── semantic_scholar.py
│   │       ├── arxiv_search.py
│   │       └── unified_search.py
│   ├── rag/               # RAG模块
│   │   └── compressor.py
│   ├── memory/            # 记忆模块
│   └── utils/             # 工具类
│       └── config.py
│
├── ui/                    # 用户界面
│   └── app.py             # Gradio Web
│
├── tests/                 # 测试
│   ├── test_intent_router.py
│   └── eval/
│       └── test_cases.json
│
└── docs/                  # 文档
    ├── architecture.md
    ├── design_decisions.md
    └── development_guide.md
```

---

## 开发规范

### 代码风格
- 使用中文注释和文档字符串
- 遵循 PEP 8（使用 ruff 检查）
- 必须添加类型注解

### 模块测试
每个模块应包含测试代码：
```python
if __name__ == "__main__":
    # 测试代码
    pass
```

### 提交规范
```
feat: 新功能
fix: 修复bug
docs: 文档更新
refactor: 重构
test: 测试
```

---

## 核心模块说明

### 1. IntentRouter (意图路由)
**文件**: `src/agents/intent_router.py`

```python
router = IntentRouter()
mode = router.route("对比Transformer和Mamba")  # -> "deep_research"
mode = router.route("Transformer是什么")       # -> "simple"
```

**路由规则**:
- 复杂关键词优先（对比、比较、综述、趋势）
- 简单关键词次之（是什么、定义、作者）
- 长度兜底（>30字符 → deep_research）

### 2. UnifiedSearch (统一搜索)
**文件**: `src/tools/search/unified_search.py`

```python
searcher = UnifiedSearch()
result = searcher.search("large language model", limit=10)
# result.papers: 论文列表
# result.sources_used: ["arxiv", "semantic_scholar"]
# result.total_count: 去重后总数
```

**特性**:
- 并行搜索多个源
- 自动去重（基于标题）
- 按引用数排序

### 3. SemanticCompressor (语义压缩)
**文件**: `src/rag/compressor.py`

```python
compressor = SemanticCompressor()
result = compressor.compress(long_text, query="attention", max_length=500)
# result.content: 压缩后内容
# result.key_points: 关键点列表
```

---

## 添加新搜索源

1. 在 `src/tools/search/` 创建新文件，如 `google_scholar.py`
2. 实现 `search()` 方法，返回 `List[Paper]`
3. 在 `unified_search.py` 的 `__init__` 中注册
4. 更新 `__init__.py` 导出

示例：
```python
# google_scholar.py
class GoogleScholarSearch:
    def search(self, query: str, limit: int = 10) -> List[Paper]:
        # 实现搜索逻辑
        pass
```

---

## 常见问题

### Q: ImportError
确保在项目根目录运行，或使用 `run.py`

### Q: 搜索无结果
检查网络连接，Semantic Scholar可能需要代理

### Q: Gradio启动失败
检查端口7860是否被占用，可用 `--port 8080` 指定其他端口

---

## 参考资源

- [Open Deep Research](https://github.com/langchain-ai/open-deep-research) - V3架构参考
- [Semantic Scholar API](https://api.semanticscholar.org/)
- [arXiv API](https://arxiv.org/help/api)
- [Gradio文档](https://gradio.app/docs/)
