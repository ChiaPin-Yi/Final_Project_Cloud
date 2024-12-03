# 使用指定版本的 Python slim 镜像
FROM python:3.9.17-slim

# 设置工作目录
WORKDIR /app

# 安装工具并清理
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && \
    rm -rf /var/lib/apt/lists/*

# 下载 Cloud SQL Proxy 并赋予权限
RUN curl -o /usr/local/bin/cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.1/cloud-sql-proxy.linux.amd64 && \
    chmod +x /usr/local/bin/cloud-sql-proxy

# 复制应用程序文件
COPY . /app

# 安装依赖
RUN pip install --no-cache-dir flask==2.2.5 mysql-connector-python==8.0.33

# 设置环境变量
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json

# 暴露 Flask 服务端口
EXPOSE 8080

# 启动服务
CMD ["sh", "-c", "cloud-sql-proxy -instances=winter-arena-443413-i7:asia-east1:showtime-1=tcp:127.0.0.1:3306 & python3 app.py"]
