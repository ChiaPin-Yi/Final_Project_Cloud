# 使用官方 Python 3.9 镜像作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件到容器中
COPY . /app

# 安装项目依赖
RUN pip install --no-cache-dir flask mysql-connector-python

# 暴露应用运行的端口（根据您的 Flask app 端口调整，默认为8080）
EXPOSE 8080

# 设置默认启动命令
CMD ["python3", "app.py"]
