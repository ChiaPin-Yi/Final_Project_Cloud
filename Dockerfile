# 使用官方 Python 3.9 Slim 镜像作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 更新系统并安装必要工具
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 下载 Cloud SQL Proxy 并赋予执行权限
RUN curl -o /usr/local/bin/cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.1/cloud-sql-proxy.linux.amd64 \
    && chmod +x /usr/local/bin/cloud-sql-proxy

# 复制项目文件到容器中
COPY . /app

# 安装项目依赖
RUN pip install --no-cache-dir flask mysql-connector-python

# 暴露应用运行的端口（根据 Flask 应用的端口，默认为 8080）
EXPOSE 8080

# 启动 Cloud SQL Proxy 和 Flask 应用
CMD ["sh", "-c", "cloud-sql-proxy -instances=winter-arena-443413-i7:asia-east1:showtime-1=tcp:3306 & python3 app.py"]
