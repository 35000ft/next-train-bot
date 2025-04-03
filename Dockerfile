FROM python:3.12

# 设置工作目录
WORKDIR /app

COPY . /app

# 列出当前目录内容，验证文件是否正确复制
RUN ls -al /app/app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 添加 Google Chrome 的 GPG key 并设置软件源
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
RUN apt-get update && apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# 安装项目依赖
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/data \
    && mkdir -p /app/log \
    && mkdir -p /app/data/schedules

# 定义容器启动时运行的命令
ENTRYPOINT ["python3", "-m","app.main"]
