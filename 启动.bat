@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo === AI Interview Agent ===
echo 自研Harness | DeepSeek | RAG | ChromaDB
echo.

REM 检查 Python 和依赖
python --version 2>&1
if errorlevel 1 (
    echo [错误] 找不到 Python，请确认已安装并加入 PATH
    pause
    exit /b
)
python -c "import streamlit" 2>&1
if errorlevel 1 (
    echo [错误] 未安装 streamlit，正在安装...
    pip install streamlit -q
)

echo.
echo 启动中...首次启动需下载 Rerank 模型和向量化知识库，约 2-3 分钟。
echo 浏览器打开 http://localhost:8502
echo.

python -m streamlit run app.py 2>&1
pause
