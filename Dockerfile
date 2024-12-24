# 使用指定版本的 Python slim 镜像
FROM python:3.9.21

# 设置工作目录
WORKDIR /app

# 安装工具、更新 pip 并清理
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && \
    python -m pip install --upgrade pip && \
    rm -rf /var/lib/apt/lists/*

# 复制当前目录内容到工作目录
COPY . /app

# 复制并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 暴露 Flask 服务端口
EXPOSE 8080

# 启动服务
CMD ["python3", "app.py"]
