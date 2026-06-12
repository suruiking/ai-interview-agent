@echo off
cd /d "%~dp0"
echo AI Interview Agent — 启动中...
echo.

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 找不到 Python
    pause
    exit
)

REM 检查 streamlit
python -c "import streamlit" >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 正在安装 streamlit...
    pip install streamlit -q
)

echo 启动 Streamlit: http://localhost:8502
echo 按 Ctrl+C 停止
echo.

python -m streamlit run app.py --server.port 8502 2>&1

pause
