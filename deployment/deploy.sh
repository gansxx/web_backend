#!/bin/bash

#############################################################################
# Web Backend 服务部署脚本
#
# 功能：
#   - 创建日志目录
#   - 安装systemd服务配置
#   - 安装logrotate日志轮转配置
#   - 启用并启动服务
#
# 使用方法：
#   sudo bash deployment/deploy.sh
#
#############################################################################

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="web_backend"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Web Backend 服务部署脚本                           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}✗ 请使用 sudo 运行此脚本${NC}"
    exit 1
fi

# 验证项目目录和环境
echo -e "${BLUE}[环境检查]${NC} 验证部署环境..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}✗ 环境变量文件不存在: $PROJECT_DIR/.env${NC}"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/run.py" ]; then
    echo -e "${RED}✗ 启动脚本不存在: $PROJECT_DIR/run.py${NC}"
    exit 1
fi

# 检查UV是否安装
UV_PATH=$(which uv 2>/dev/null || echo "")
if [ -z "$UV_PATH" ]; then
    echo -e "${RED}✗ 找不到UV命令，请先安装UV${NC}"
    echo -e "${YELLOW}安装方法: curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} UV路径: $UV_PATH"

echo -e "${YELLOW}📂 项目目录: ${PROJECT_DIR}${NC}"
echo ""

# 1. 创建日志目录
echo -e "${BLUE}[1/6]${NC} 创建日志目录..."
LOG_DIR="/var/log/${SERVICE_NAME}"
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
    chmod 755 "$LOG_DIR"
    echo -e "${GREEN}✓${NC} 日志目录创建成功: $LOG_DIR"
else
    echo -e "${GREEN}✓${NC} 日志目录已存在: $LOG_DIR"
fi
echo ""

# 2. 安装systemd服务文件
echo -e "${BLUE}[2/6]${NC} 安装systemd服务配置..."
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
if [ -f "$SCRIPT_DIR/${SERVICE_NAME}.service" ]; then
    cp "$SCRIPT_DIR/${SERVICE_NAME}.service" "$SERVICE_FILE"
    chmod 644 "$SERVICE_FILE"
    echo -e "${GREEN}✓${NC} 服务文件已安装: $SERVICE_FILE"
else
    echo -e "${RED}✗ 服务文件不存在: $SCRIPT_DIR/${SERVICE_NAME}.service${NC}"
    exit 1
fi
echo ""

# 3. 安装logrotate配置
echo -e "${BLUE}[3/6]${NC} 安装logrotate配置..."
LOGROTATE_FILE="/etc/logrotate.d/${SERVICE_NAME}"
if [ -f "$SCRIPT_DIR/${SERVICE_NAME}.logrotate" ]; then
    cp "$SCRIPT_DIR/${SERVICE_NAME}.logrotate" "$LOGROTATE_FILE"
    chmod 644 "$LOGROTATE_FILE"
    echo -e "${GREEN}✓${NC} Logrotate配置已安装: $LOGROTATE_FILE"
else
    echo -e "${YELLOW}⚠${NC} Logrotate配置文件不存在，跳过"
fi
echo ""

# 4. 重载systemd
echo -e "${BLUE}[4/6]${NC} 重载systemd配置..."
systemctl daemon-reload
echo -e "${GREEN}✓${NC} Systemd配置已重载"
echo ""

# 5. 启用服务（开机自启）
echo -e "${BLUE}[5/6]${NC} 启用服务开机自启..."
systemctl enable "${SERVICE_NAME}.service"
echo -e "${GREEN}✓${NC} 服务已设置为开机自启"
echo ""

# 6. 启动服务
echo -e "${BLUE}[6/6]${NC} 启动服务..."
if systemctl is-active --quiet "${SERVICE_NAME}.service"; then
    echo -e "${YELLOW}⚠${NC} 服务已在运行，正在重启..."
    systemctl restart "${SERVICE_NAME}.service"
else
    systemctl start "${SERVICE_NAME}.service"
fi

# 等待服务启动
sleep 2

# 检查服务状态
if systemctl is-active --quiet "${SERVICE_NAME}.service"; then
    echo -e "${GREEN}✓${NC} 服务启动成功"
else
    echo -e "${RED}✗${NC} 服务启动失败"
    echo -e "${YELLOW}查看错误日志：${NC}"
    echo -e "  journalctl -u ${SERVICE_NAME}.service -n 50 --no-pager"
    exit 1
fi
echo ""

# 显示服务状态
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    部署完成                                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}服务状态：${NC}"
systemctl status "${SERVICE_NAME}.service" --no-pager -l
echo ""

# 显示常用命令
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                   常用管理命令                             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}查看服务状态：${NC}"
echo "  systemctl status ${SERVICE_NAME}.service"
echo ""
echo -e "${YELLOW}查看实时日志：${NC}"
echo "  journalctl -u ${SERVICE_NAME}.service -f"
echo ""
echo -e "${YELLOW}重启服务：${NC}"
echo "  systemctl restart ${SERVICE_NAME}.service"
echo ""
echo -e "${YELLOW}停止服务：${NC}"
echo "  systemctl stop ${SERVICE_NAME}.service"
echo ""
echo -e "${YELLOW}查看日志文件：${NC}"
echo "  tail -f /var/log/${SERVICE_NAME}/web_backend.log"
echo "  tail -f /var/log/${SERVICE_NAME}/web_backend_error.log"
echo ""
