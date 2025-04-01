FROM python:3.12

# 设置工作目录
WORKDIR /app

COPY . /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 列出当前目录内容，验证文件是否正确复制
RUN ls -la

# 安装项目依赖
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/temp \
    && mkdir -p /app/log

# 定义容器启动时运行的命令
ENTRYPOINT ["python3", "-m","app.main"]
