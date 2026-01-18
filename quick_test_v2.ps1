# V2架构快速测试脚本 (PowerShell)
# 用法: .\quick_test_v2.ps1

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "V2 架构快速测试" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

# 1. 测试导入
Write-Host "[1/3] 测试模块导入..." -ForegroundColor Yellow
python test_import.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 模块导入失败！" -ForegroundColor Red
    Write-Host "请检查 V2 模块是否正确创建" -ForegroundColor Red
    exit 1
}

Write-Host "✓ 模块导入成功" -ForegroundColor Green
Write-Host ""

# 2. 检查API Key
Write-Host "[2/3] 检查API配置..." -ForegroundColor Yellow
$apiCheck = python -c "from dotenv import load_dotenv; import os; load_dotenv(); key=os.getenv('QWEN_API_KEY'); print('OK' if key else 'NO')"

if ($apiCheck -eq "NO") {
    Write-Host "⚠️  未配置 QWEN_API_KEY" -ForegroundColor Yellow
    Write-Host "   将使用回退方案（报告质量较低）" -ForegroundColor Yellow
} else {
    Write-Host "✓ API Key 已配置" -ForegroundColor Green
}
Write-Host ""

# 3. 启动Web界面
Write-Host "[3/3] 启动Web界面..." -ForegroundColor Yellow
Write-Host "访问 http://127.0.0.1:7860" -ForegroundColor Cyan
Write-Host ""
Write-Host "测试清单：" -ForegroundColor Yellow
Write-Host "  1. 检查 '深度研究' Tab 中是否有 V2 checkbox" -ForegroundColor White
Write-Host "  2. 勾选 V2，输入查询（如：对比 Transformer 和 RNN）" -ForegroundColor White
Write-Host "  3. 查看报告是否显示 '思考过程'（V2特有）" -ForegroundColor White
Write-Host "  4. 不勾选 V2，同样查询，对比输出差异" -ForegroundColor White
Write-Host ""
Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Yellow
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

python run.py --web
