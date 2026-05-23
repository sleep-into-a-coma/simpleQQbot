#!/usr/bin/env bash
# SP-Bot + NapCat 一键安装脚本
# 支持 Ubuntu 22.04+/Debian 12+
# 用法：bash install.sh
# 注意：NapCat v4.x 需要 Node.js 18+ 和 Linux QQNT
set -e
OFFLINE=false

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
        *)
            log_error "不支持的操作系统: $OS"
            log_error "支持: Ubuntu 22.04+, Debian 12+"
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
        sudo apt install -y python3 python3-venv python3-pip git wget curl unzip nodejs xvfb libgtk-3-0 libnotify4 libnss3 libxss1 libxtst6 xdg-utils libatspi2.0-0 libsecret-1-0
    else
        log_error "当前仅支持 Debian/Ubuntu 系统"
        exit 1
    fi

    # Verify Node.js >= 18
    NODE_VER=$(node -v 2>/dev/null | sed 's/v//' | cut -d. -f1)
    if [ -z "$NODE_VER" ] || [ "$NODE_VER" -lt 18 ]; then
        log_info "安装 Node.js 20.x..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt install -y nodejs
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
    if $OFFLINE; then
        if [ ! -d "wheels" ]; then
            log_error "离线模式需要 wheels/ 目录，但未找到"
            log_error "请确保完整包已正确解压"
            exit 1
        fi
        log_info "离线模式：从 wheels/ 安装依赖..."
        pip install --no-index --find-links=wheels/ -e .
    else
        pip install -e .
    fi
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
SEARCH_BACKEND=duckduckgo
SEARCH_MAX_RESULTS=5
ONEBOT_WS_PORT=8989
PORT=8989
ENVEOF
    log_info ".env 已生成，其他模型可稍后手动编辑"
}

# ============================================================
# 4. 安装 Linux QQNT
# ============================================================
install_qqnt() {
    if command -v qq &>/dev/null; then
        log_info "QQNT 已安装，跳过"
        return
    fi

    log_info "安装 Linux QQNT..."
    QQ_DEB="/tmp/linuxqq_amd64.deb"
    QQ_URL="https://dldir1.qq.com/qqfile/qq/QQNT/94704804/linuxqq_3.2.23-44343_amd64.deb"
    wget -q --show-progress "$QQ_URL" -O "$QQ_DEB" || {
        log_error "QQNT 下载失败"
        exit 1
    }
    sudo dpkg -i "$QQ_DEB" || sudo apt install -f -y
    rm -f "$QQ_DEB"
    log_info "QQNT 安装完成"
}

# ============================================================
# 5. 下载NapCat
# ============================================================
install_napcat() {
    NAPCAT_DIR="$HOME/napcat"
    if [ -d "$NAPCAT_DIR" ] && [ -f "$NAPCAT_DIR/napcat.mjs" ]; then
        log_info "NapCat 已安装，跳过"
        return
    fi

    if $OFFLINE; then
        log_info "离线模式：从本地安装 NapCat..."
        if [ ! -f "napcat/NapCat.Shell.zip" ]; then
            log_error "未找到 napcat/NapCat.Shell.zip，离线安装失败"
            log_error "请确保完整包已正确解压"
            exit 1
        fi
        mkdir -p "$NAPCAT_DIR"
        unzip -qo "napcat/NapCat.Shell.zip" -d "$NAPCAT_DIR"
        log_info "NapCat 安装完成: $NAPCAT_DIR"
        return
    fi

    log_info "下载 NapCat..."
    mkdir -p "$NAPCAT_DIR"

    NAPCAT_URL="https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.Shell.zip"

    log_info "下载: $NAPCAT_URL"
    wget -q --show-progress "$NAPCAT_URL" -O /tmp/napcat.zip || {
        log_error "下载失败，请检查网络或手动下载 NapCat 到 $NAPCAT_DIR"
        log_error "NapCat releases: https://github.com/NapNeko/NapCatQQ/releases"
        exit 1
    }

    unzip -qo /tmp/napcat.zip -d "$NAPCAT_DIR"
    rm -f /tmp/napcat.zip
    log_info "NapCat 安装完成: $NAPCAT_DIR"
}

# ============================================================
# 6. 写入NapCat配置
# ============================================================
configure_napcat() {
    NAPCAT_CONFIG_DIR="$HOME/napcat/config"
    mkdir -p "$NAPCAT_CONFIG_DIR"

    # Check for existing config
    EXISTING=$(ls "$NAPCAT_CONFIG_DIR"/onebot11_*.json 2>/dev/null | head -1)
    if [ -n "$EXISTING" ]; then
        log_info "NapCat 配置已存在: $EXISTING，跳过"
        return
    fi

    read -p "请输入机器人QQ号: " qq_number
    if [ -z "$qq_number" ]; then
        log_error "QQ号不能为空"
        exit 1
    fi

    if [ -f ".env" ]; then
        set -a; source .env; set +a
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
# 7. 安装systemd服务
# ============================================================
install_services() {
    PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
    CURRENT_USER=$(whoami)
    NAPCAT_DIR="$HOME/napcat"

    # === sp-bot.service ===
    sudo tee /etc/systemd/system/sp-bot.service > /dev/null << BOTEOF
[Unit]
Description=SP-Bot
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
SyslogIdentifier=sp-bot

[Install]
WantedBy=multi-user.target
BOTEOF

    # === napcat.service (NapCat v4.x) ===
    sudo tee /etc/systemd/system/napcat.service > /dev/null << NAPEOF
[Unit]
Description=NapCat QQ Client
After=sp-bot.service
Wants=sp-bot.service

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${NAPCAT_DIR}
ExecStart=/usr/bin/node ${NAPCAT_DIR}/napcat.mjs
Environment=NAPCAT_WRAPPER_PATH=/opt/QQ/resources/app/wrapper.node
Environment=NAPCAT_QQ_PACKAGE_INFO_PATH=/opt/QQ/resources/app/package.json
Environment=NAPCAT_QQ_VERSION_CONFIG_PATH=/opt/QQ/resources/app/versions/config.json
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
    sudo systemctl enable sp-bot napcat

    log_info "systemd 服务已安装并启用开机自启"
}

# ============================================================
# 8. 启动服务
# ============================================================
start_services() {
    log_info "启动服务..."
    sudo systemctl start sp-bot
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
    echo "  查看Bot状态:  sudo systemctl status sp-bot"
    echo "  查看NapCat:   sudo systemctl status napcat"
    echo "  实时日志:     sudo journalctl -u sp-bot -f"
    echo "               sudo journalctl -u napcat -f"
    echo "  停止:         sudo systemctl stop sp-bot napcat"
    echo "  卸载:         sudo systemctl disable --now sp-bot napcat"
    echo "               sudo rm /etc/systemd/system/sp-bot.service"
    echo "               sudo rm /etc/systemd/system/napcat.service"
}

# ============================================================
# 主流程
# ============================================================
main() {
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    cd "$PROJECT_DIR"

    OFFLINE=false
    if [ "${1:-}" = "--offline" ]; then
        OFFLINE=true
    fi

    echo ""
    echo "========================================"
    echo "  SP-Bot + NapCat 一键安装"
    echo "========================================"
    echo ""

    if $OFFLINE; then
        log_info "离线模式：跳过系统依赖安装（请确保 python3/nodejs 已安装）"
    else
        detect_os
        install_system_deps
        install_qqnt
    fi
    setup_venv
    setup_env
    install_napcat
    configure_napcat
    install_services
    start_services
}

main "$@"
