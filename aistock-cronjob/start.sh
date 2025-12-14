#!/bin/bash

# 启动脚本
echo "Starting AI Stock Cron Service..."

# 设置环境变量
export PYTHONPATH="/app:$PYTHONPATH"

# 查找python路径并导出
export PYTHON_PATH=$(which python)
echo "Using Python executable: $PYTHON_PATH"

# 启动cron服务
service cron start

# 创建日志文件
touch /var/log/cron/hot_stock.log
touch /var/log/cron/realtime_quotes.log
touch /var/log/cron/index.log
touch /var/log/cron/news.log
touch /var/log/cron/stock_info.log
touch /var/log/cron/stock_history.log
touch /var/log/cron/wechat_morning.log
touch /var/log/cron/wechat_push.log
touch /var/log/cron/tags_stocks.log
touch /var/log/cron/stock_eva.log
touch /var/log/cron/stock_news.log
touch /var/log/cron/stock_name.log
touch /var/log/cron/cache_clean.log
touch /var/log/cron/cache_stock_detail_page.log
touch /var/log/cron/log_cleanup.log
touch /var/log/cron/cleanup_old_news.log

# 输出启动信息
echo "AI Stock Cron Service started at $(date)"
echo "Monitoring cron logs..."

# 保持容器运行并输出日志
tail -f /var/log/cron/*.log &

# 等待信号
wait
