# ==================== 第一阶段：装依赖 ====================
FROM python:3.10-slim AS builder

WORKDIR /app

# 先装依赖（这层有缓存，代码改了不重建）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==================== 第二阶段：运行镜像 ====================
FROM python:3.10-slim

WORKDIR /app

# 从 builder 阶段复制已装好的依赖（减小镜像体积）
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 拷贝项目代码
COPY . .

# Streamlit 端口
EXPOSE 8502

# 启动
CMD ["streamlit", "run", "app.py", "--server.port=8502", "--server.address=0.0.0.0"]
