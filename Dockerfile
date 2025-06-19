FROM python:3.12-bullseye AS bot-base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 添加 Google Chrome 的 GPG key 并设置软件源
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
RUN apt-get update && \
apt-get install -y locales fonts-noto-cjk && \
sed -i '/zh_CN.UTF-8/s/^# //g' /etc/locale.gen && \
locale-gen zh_CN.UTF-8 && \
update-locale LANG=zh_CN.UTF-8 && \
apt-get install -y google-chrome-stable && \
rm -rf /var/lib/apt/lists/*

# 设置环境变量
ENV LANG='zh_CN.UTF-8'
ENV LANGUAGE='zh_CN:zh:en_US:en'
ENV LC_ALL='zh_CN.UTF-8'
COPY /requirements.txt /app/requirements.txt
COPY /github_requirements.txt /app/github_requirements.txt

# 安装项目依赖
RUN pip install --no-cache-dir -r /app/requirements.txt

FROM bot-base

COPY . /app
WORKDIR /app
RUN pip install uvicorn

RUN mkdir -p /app/data \
    && mkdir -p /app/log \
    && mkdir -p /app/data/schedules \
    && mkdir -p /app/data/ticket-prices\
    && mkdir -p /app/data/templates
RUN pip install --no-cache-dir -r /app/github_requirements.txt

EXPOSE 8260
# 定义容器启动时运行的命令
CMD ["uvicorn", "app.wechat_bot:app", "--host", "0.0.0.0", "--port", "8260"]
