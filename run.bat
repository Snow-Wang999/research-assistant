@echo off
REM 科研助手启动脚本 (Windows)
REM 使用方法:
REM   run.bat           - 启动CLI
REM   run.bat web       - 启动Web界面
REM   run.bat web share - 启动Web并生成公开链接

cd /d "%~dp0"

REM 检查虚拟环境
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [警告] 未找到虚拟环境，请先运行:
    echo   uv venv
    echo   .venv\Scripts\activate
    echo   uv sync
    echo.
)

if "%1"=="web" (
    if "%2"=="share" (
        python run.py --web --share
    ) else (
        python run.py --web
    )
) else (
    python run.py
)
