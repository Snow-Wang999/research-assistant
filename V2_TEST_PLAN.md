# V2架构测试计划 (PowerShell)

## 📋 快速开始

```powershell
# 1. 测试导入
python test_import.py

# 2. 启动Web界面
python run.py --web

# 3. 浏览器访问 http://127.0.0.1:7860
```

---

## 1. 环境检查

```powershell
# 检查Python版本
python --version  # 应该 >= 3.10

# 检查依赖
python -m pip list | Select-String -Pattern "httpx|gradio|arxiv"
```

## 2. 模块导入测试

```powershell
# 运行导入测试
python test_import.py
```

**预期输出：**
```
Testing imports...
1. Importing V2 state...
   ✓ state OK
2. Importing V2 tools...
   ✓ tools OK
3. Importing V2 prompts...
   ✓ prompts OK
4. Importing V2 researcher...
   ✓ researcher OK
5. Importing V2 supervisor...
   ✓ supervisor OK
6. Importing V2 orchestrator...
   ✓ orchestrator OK
7. Importing main V2 package...
   ✓ V2 package OK

All imports successful!
```

## 3. Web界面启动

```powershell
python run.py --web
```

**预期输出：**
```
==================================================
科研助手 v0.1.0
==================================================

启动模式: Web界面
端口: 7860

Running on local URL:  http://127.0.0.1:7860
```

访问 http://127.0.0.1:7860

### 界面检查清单

在"深度研究"Tab中应该看到：
- [ ] 研究问题输入框
- [ ] "📄 使用全文研究" checkbox
- [ ] "🔄 使用 V2 架构 (Supervisor 循环，动态决策研究轮数)" checkbox ← **新增**
- [ ] "🚀 开始研究" 按钮

## 4. 功能测试

### 测试用例 1：V2 模式

1. 输入查询：**"对比 Transformer 和 RNN 的优劣"**
2. ✅ **勾选** V2 checkbox
3. 点击 "开始研究"

**预期结果：**
- 显示 "🚀 深度研究 (V2 Supervisor 循环)"
- 报告区显示：
  ```
  ## 🧠 思考过程  ← V2特有
  1. ...
  2. ...

  ## 研究报告
  ...

  ## 参考来源
  ...

  ---
  总耗时: XX秒 | 研究轮数: X轮 | 论文: X篇  ← V2元数据
  完成原因: ...
  ```

### 测试用例 2：V1 模式（对照组）

1. 输入查询：**"对比 Transformer 和 RNN 的优劣"**
2. ❌ **不勾选** V2 checkbox
3. 点击 "开始研究"

**预期结果：**
- 显示 "🚀 深度研究"
- 报告区显示：
  ```
  ## 📋 问题分解  ← V1特有
  问题类型: ...
  研究策略: ...
  子问题:
  1. ...
  2. ...

  ## 研究报告
  ...

  ---
  总耗时: XX秒 | 子问题: 3个 | 论文: X篇  ← V1元数据
  各阶段耗时:
  - ...
  ```

### 测试用例 3：V2 + 全文模式

1. 输入查询：**"BERT预训练方法的原理"**
2. ✅ 同时勾选：V2 + 全文研究
3. 点击 "开始研究"

**预期结果：**
- 显示 "🚀 深度研究 (V2 Supervisor 循环) (📄 全文模式)"
- 耗时更长（下载PDF）
- 报告质量更高

### 测试用例 4：停止功能

1. 开始任意研究
2. 点击 "⏹️ 停止"

**预期结果：**
- 研究立即中止
- 显示部分结果

## 5. 对比测试（V1 vs V2）

使用相同查询测试两种模式，记录对比数据：

| 项目 | V1 模式 | V2 模式 | 说明 |
|------|---------|---------|------|
| 决策方式 | 固定3个子问题 | 动态X轮 | V2自适应 |
| 思考过程 | 隐式（内置） | 显式（think_tool） | V2可见 |
| 报告结构 | 问题分解 + 报告 | 思考过程 + 报告 | 不同展示 |
| 元数据 | 子问题数 + 阶段耗时 | 轮数 + 完成原因 | 不同指标 |
| 灵活性 | 固定流程 | 动态调整 | V2更灵活 |

## 6. 故障排查 (PowerShell)

### 导入失败

```powershell
# 手动测试导入
python -c "import sys; sys.path.insert(0, 'src'); from agents.deep_research.v2 import DeepResearchV2; print('✓ 导入成功')"
```

### 端口被占用

```powershell
# 检查端口
netstat -an | Select-String ":7860"

# 更换端口
python run.py --web --port 8080
```

### API Key未配置

```powershell
# 检查环境变量
python -c "from dotenv import load_dotenv; import os; load_dotenv(); key=os.getenv('QWEN_API_KEY'); print('QWEN_API_KEY:', key[:10] + '...' if key else '❌ 未设置')"
```

如果未设置，编辑 `.env` 文件：
```
QWEN_API_KEY=sk-xxxxxxxxxx
```

### 依赖缺失

```powershell
# 安装依赖
pip install httpx gradio python-dotenv arxiv pymupdf

# 或使用 uv (更快)
uv sync
```

## 7. 测试通过标准

- [ ] ✓ 所有模块正常导入 (`test_import.py` 通过)
- [ ] ✓ Web界面正常启动 (访问 http://127.0.0.1:7860)
- [ ] ✓ V2 checkbox 显示正确
- [ ] ✓ V1 模式正常工作（显示问题分解）
- [ ] ✓ V2 模式正常工作（显示思考历史）
- [ ] ✓ V1/V2 输出格式明显不同
- [ ] ✓ 停止按钮正常工作
- [ ] ✓ 错误处理正确（无崩溃）

## 8. 预期日志输出

启动后，控制台应该显示：

```
[V2] 开始深度研究: 对比 Transformer...
[Supervisor] === 第 1 轮 ===
[Supervisor] 思考: 需要从架构、训练、性能三个维度对比...
[Supervisor] 派发研究: Transformer架构特点
[Researcher] 开始研究: Transformer架构特点
[Researcher] 完成研究: Transformer架构特点, 筛选 5/15 篇
[Supervisor] === 第 2 轮 ===
[Supervisor] 思考: 已有架构信息，需要补充性能对比...
...
[Supervisor] 研究完成: 已收集足够信息
[V2] 正在生成研究报告...
[V2] 研究完成
```

## 9. 常见问题

### Q: V2 checkbox 没有显示？
A: 检查 `ui/app.py` 是否正确添加了 checkbox（约第469行）

### Q: 点击V2 checkbox后没反应？
A: 检查事件绑定是否包含 `use_v2_checkbox`（约第574、582行）

### Q: 报告没有显示思考过程？
A: 检查 `app.py` 约第232-239行，确保 V2 模式显示 `thinking_history`

### Q: 显示 "LLM 调用失败"？
A: 检查 `.env` 中的 `QWEN_API_KEY` 是否正确

## 10. 下一步

测试通过后，可以：

1. **性能优化**：比较V1/V2的实际效果
2. **参数调整**：修改 `max_rounds`（默认10轮）
3. **Prompt优化**：调整 Supervisor/Researcher prompt
4. **文档更新**：更新 README 和 CHANGELOG
5. **发布**：准备 v0.4.5 版本发布

---

**测试完成后，请更新 TODO.md 并标记 "测试 V2 架构" 为完成。**
