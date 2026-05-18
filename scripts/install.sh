#!/usr/bin/env bash
# QQBot AI + NapCat 一键安装脚本
# 支持 Ubuntu 22.04+/Debian 12+/CentOS 8+
# 用法：bash install.sh
set -e

# ============================================================
# 颜色定义
# ============================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================
# 0. 检测OS
# ============================================================
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        log_error "无法识别操作系统"
        exit 1
    fi

    case "$OS" in
        ubuntu|debian) PKG_MGR="apt";;
        centos|rhel|fedora) PKG_MGR="yum";;
        *)
            log_error "不支持的操作系统: $OS"
            log_error "支持: Ubuntu 22.04+, Debian 12+, CentOS 8+"
            exit 1
            ;;
    esac
    log_info "检测到: $OS $VER (包管理器: $PKG_MGR)"
}

# ============================================================
# 1. 安装系统依赖
# ============================================================
install_system_deps() {
    log_info "安装系统依赖..."
    if [ "$PKG_MGR" = "apt" ]; then
        sudo apt update
        sudo apt install -y python3 python3-venv python3-pip git wget curl screen
    else
        sudo yum install -y python3 python3-pip git wget curl screen
    fi
    log_info "系统依赖安装完成"
}

# ============================================================
# 2. 创建Python虚拟环境
# ============================================================
setup_venv() {
    log_info "创建Python虚拟环境..."
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    source .venv/bin/activate
    pip install -e .
    log_info "Python依赖安装完成"
}

# ============================================================
# 3. 生成.env
# ============================================================
setup_env() {
    if [ -f ".env" ]; then
        log_info ".env 已存在，跳过"
        return
    fi
    log_info "=== .env 配置 ==="
    read -p "请输入默认模型字母 (如 A): " default_model
    default_model=${default_model:-A}
    read -p "请输入模型名称 (如 deepseek-chat): " model_name
    read -p "请输入API Base URL: " api_base
    read -p "请输入API Key: " api_key

    cat > .env << ENVEOF
DEFAULT_MODEL=${default_model}
MODEL_${default_model}_NAME=${model_name}
MODEL_${default_model}_PROVIDER=openai_compat
MODEL_${default_model}_API_BASE=${api_base}
MODEL_${default_model}_API_KEY=${api_key}
MODEL_${default_model}_VISION=false
SEARCH_ENABLED=true
SEARCH_MAX_RESULTS=5
ONEBOT_WS_PORT=8989
ENVEOF
    log_info ".env 已生成，其他模型可稍后手动编辑"
}

# ============================================================
# 4. 下载NapCat
# ============================================================
install_napcat() {
    NAPCAT_DIR="$HOME/napcat"
    if [ -d "$NAPCAT_DIR" ] && [ -f "$NAPCAT_DIR/napcat" ]; then
        log_info "NapCat 已安装，跳过"
        return
    fi

    log_info "下载 NapCat..."
    mkdir -p "$NAPCAT_DIR"

    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  NAPCAT_ARCH="amd64";;
        aarch64) NAPCAT_ARCH="arm64";;
        *)
            log_error "不支持的CPU架构: $ARCH"
            log_error "NapCat 支持: x86_64, aarch64"
            exit 1
            ;;
    esac

    NAPCAT_URL="https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.linux-${NAPCAT_ARCH}.tar.gz"

    log_info "下载: $NAPCAT_URL"
    wget -q --show-progress "$NAPCAT_URL" -O /tmp/napcat.tar.gz || {
        log_error "下载失败，请检查网络或手动下载 NapCat 到 $NAPCAT_DIR"
        log_error "NapCat releases: https://github.com/NapNeko/NapCatQQ/releases"
        exit 1
    }

    tar -xzf /tmp/napcat.tar.gz -C "$NAPCAT_DIR"
    rm -f /tmp/napcat.tar.gz
    chmod +x "$NAPCAT_DIR/napcat"
    log_info "NapCat 安装完成: $NAPCAT_DIR"
}

# ============================================================
# 5. 写入NapCat配置
# ============================================================
configure_napcat() {
    NAPCAT_CONFIG_DIR="$HOME/napcat/config"
    mkdir -p "$NAPCAT_CONFIG_DIR"

    read -p "请输入机器人QQ号: " qq_number
    if [ -z "$qq_number" ]; then
        log_error "QQ号不能为空"
        exit 1
    fi

    PORT="${ONEBOT_WS_PORT:-8989}"
    CONFIG_FILE="$NAPCAT_CONFIG_DIR/onebot11_${qq_number}.json"

    cat > "$CONFIG_FILE" << CONFEOF
{
    "enableWsReverse": true,
    "wsReverseUrls": ["ws://127.0.0.1:${PORT}/onebot/v11/ws"],
    "enableHttp": false,
    "enableWs": false,
    "messagePostFormat": "array",
    "heartInterval": 30000,
    "token": "",
    "debug": false
}
CONFEOF
    log_info "NapCat 配置写入: $CONFIG_FILE"
}

# ============================================================
# 6. 安装systemd服务
# ============================================================
install_services() {
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    PYTHON_BIN="$(pwd)/.venv/bin/python"
    CURRENT_USER=$(whoami)

    # === qqbot.service ===
    sudo tee /etc/systemd/system/qqbot.service > /dev/null << BOTEOF
[Unit]
Description=QQBot AI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PYTHON_BIN} bot.py
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=10
StartLimitBurst=10
StartLimitIntervalSec=300
StandardOutput=journal
StandardError=journal
SyslogIdentifier=qqbot

[Install]
WantedBy=multi-user.target
BOTEOF

    # === napcat.service ===
    NAPCAT_DIR="$HOME/napcat"
    sudo tee /etc/systemd/system/napcat.service > /dev/null << NAPEOF
[Unit]
Description=NapCat QQ Client
After=qqbot.service
Wants=qqbot.service

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${NAPCAT_DIR}
ExecStart=${NAPCAT_DIR}/napcat
Restart=on-failure
RestartSec=10
StartLimitBurst=10
StartLimitIntervalSec=300
StandardOutput=journal
StandardError=journal
SyslogIdentifier=napcat

[Install]
WantedBy=multi-user.target
NAPEOF

    sudo systemctl daemon-reload
    sudo systemctl enable qqbot napcat

    log_info "systemd 服务已安装并启用开机自启"
}

# ============================================================
# 7. 启动服务
# ============================================================
start_services() {
    log_info "启动服务..."
    sudo systemctl start qqbot
    sleep 2
    sudo systemctl start napcat
    sleep 3

    echo ""
    echo "============================================"
    echo "  安装完成！"
    echo "============================================"
    echo ""
    echo "扫码登录："
    echo "  sudo journalctl -u napcat -f"
    echo "  （看日志中的二维码链接，用QQ小号扫码）"
    echo ""
    echo "常用命令："
    echo "  查看Bot状态:  sudo systemctl status qqbot"
    echo "  查看NapCat:   sudo systemctl status napcat"
    echo "  实时日志:     sudo journalctl -u qqbot -f"
    echo "               sudo journalctl -u napcat -f"
    echo "  停止:         sudo systemctl stop qqbot napcat"
    echo "  卸载:         sudo systemctl disable --now qqbot napcat"
    echo "               sudo rm /etc/systemd/system/qqbot.service"
    echo "               sudo rm /etc/systemd/system/napcat.service"
}

# ============================================================
# 主流程
# ============================================================
main() {
    echo ""
    echo "========================================"
    echo "  QQBot AI + NapCat 一键安装"
    echo "========================================"
    echo ""

    detect_os
    install_system_deps
    setup_venv
    setup_env
    install_napcat
    configure_napcat
    install_services
    start_services
}

main
