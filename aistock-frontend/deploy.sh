#!/bin/bash

# 定义颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# 定义路径
SOURCE_DIR="/Users/fwm/projects/dbproj-aistock/aistock-frontend"
DIST_DIR="$SOURCE_DIR/dist"
REMOTE_HOST="ali_hk"
REMOTE_DIR="/opt/aistock"

# 显示开始信息
echo -e "${YELLOW}=== 开始部署 AI Stock Link 前端项目 ===${NC}"

# 进入前端项目目录
echo -e "进入项目目录: ${SOURCE_DIR}"
cd $SOURCE_DIR || { echo -e "${RED}错误: 无法进入前端项目目录${NC}"; exit 1; }

# 构建Vue项目
echo -e "${YELLOW}开始构建Vue项目...${NC}"
npm run build || { echo -e "${RED}错误: Vue项目构建失败${NC}"; exit 1; }
echo -e "${GREEN}Vue项目构建成功!${NC}"

# 部署到远程服务器
echo -e "${YELLOW}开始部署到远程服务器 ${REMOTE_HOST}...${NC}"

# 1. 清理远程目录
echo -e "清理远程目录: ${REMOTE_DIR}..."
ssh $REMOTE_HOST "mkdir -p $REMOTE_DIR && rm -rf $REMOTE_DIR/*" || { echo -e "${RED}错误: 无法清理远程目录${NC}"; exit 1; }

# 2. 上传文件
echo -e "上传文件到远程服务器..."
scp -r $DIST_DIR/* $REMOTE_HOST:$REMOTE_DIR/ || { echo -e "${RED}错误: 文件上传失败${NC}"; exit 1; }

# 3. 设置权限
echo -e "设置远程文件权限..."
ssh $REMOTE_HOST "find $REMOTE_DIR -type d -exec chmod 755 {} \; && find $REMOTE_DIR -type f -exec chmod 644 {} \;" || { echo -e "${RED}错误: 设置权限失败${NC}"; exit 1; }

# 删除dist目录
echo -e "删除本地dist目录..."
rm -rf $DIST_DIR || { echo -e "${RED}错误: 删除dist目录失败${NC}"; exit 1; }

# 显示完成信息
echo -e "${GREEN}=== 部署完成! ===${NC}"
echo -e "Vue应用已成功部署到: ${REMOTE_HOST}:${REMOTE_DIR}"
