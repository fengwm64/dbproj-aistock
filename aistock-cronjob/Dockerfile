FROM python:3.10-slim

# 设置时区为上海时间
ENV TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    dpkg-reconfigure -f noninteractive tzdata

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential gcc g++ python3-dev cron mariadb-client \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY . .

# 安装Python依赖
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 创建日志目录
RUN mkdir -p /var/log/cron

# 复制cron配置文件
COPY crontab /etc/cron.d/aistock-cron

# 设置cron文件权限
RUN chmod 0644 /etc/cron.d/aistock-cron

# 应用cron作业
RUN crontab /etc/cron.d/aistock-cron

# 创建启动脚本
RUN chmod +x /app/start.sh

# 启动命令
CMD ["/bin/bash", "/app/start.sh"]
