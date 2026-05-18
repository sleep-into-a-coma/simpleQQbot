# NapCat + NoneBot 一键部署 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 NapCat 和 NoneBot bot 打包为一键部署方案，同时支持 Docker Compose 和裸机脚本。

**Architecture:** 反向 WebSocket 模式（NapCat 作为 WS 客户端连接 NoneBot 的 8989 端口）。Docker 用 `mlikiowa/napcat-docker` 镜像通过环境变量配置；裸机用 NapCat 二进制 + systemd。bot 侧只改 `bot.py`（补 dotenv）和 `Dockerfile`（加 HEALTHCHECK）。

**Tech Stack:** Docker Compose, bash, NoneBot2, NapCat (mlikiowa/napcat-docker)

---

### Task 1: 修改 bot.py — 补 dotenv 加载

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: 在 bot.py 顶部加 dotenv 加载**

`bot.py` 当前内容：
```python
import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

nonebot.load_plugins("src/plugins")

if __name__ == "__main__":
    nonebot.run()
```

改为：
```python
from dotenv import load_dotenv
load_dotenv()

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

nonebot.load_plugins("src/plugins")

if __name__ == "__main__":
    nonebot.run()
```

- [ ] **Step 2: 验证语法正确**

Run: `python -c "import ast; ast.parse(open('bot.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add bot.py
git commit -m "fix: add dotenv loading to bot.py for bare-metal deployment"
```

---

### Task 2: 修改 Dockerfile — 加 HEALTHCHECK

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: 在 Dockerfile 末尾加 HEALTHCHECK**

`Dockerfile` 当前内容：
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

CMD ["nb", "run"]
```

改为：
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('127.0.0.1', 8989)); s.close()"

CMD ["nb", "run"]
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile
git commit -m "feat: add HEALTHCHECK for NoneBot WS port 8989"
```

---

### Task 3: 修改 docker-compose.yml — 加 napcat 服务和 internal network

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: 重写 docker-compose.yml**

`docker-compose.yml` 当前内容：
```yaml
services:
  qqbot:
    build: .
    volumes:
      - ./config:/app/config:ro
      - ./data:/app/data
      - ./.env:/app/.env:ro
    restart: unless-stopped
```

改为：
```yaml
services:
  bot:
    build: .
    volumes:
      - ./config:/app/config:ro
      - ./data:/app/data
      - ./.env:/app/.env:ro
    networks:
      - qqbot-net
    restart: unless-stopped

  napcat:
    image: mlikiowa/napcat-docker:latest
    environment:
      - WSR_ENABLE=true
      - WS_URLS=["ws://bot:8989/onebot/v11/ws"]
      - MESSAGE_POST_FORMAT=array
      - WEBUI_TOKEN=napcat
      - NAPCAT_UID=0
      - NAPCAT_GID=0
    ports:
      - "6099:6099"
    volumes:
      - ./napcat/QQ:/app/.config/QQ
      - ./napcat/config:/app/napcat/config
    networks:
      - qqbot-net
    depends_on:
      bot:
        condition: service_healthy
    restart: unless-stopped

networks:
  qqbot-net:
    driver: bridge
```

> **说明：** NapCat 配置走环境变量（`WSR_ENABLE` + `WS_URLS`），比挂载 config 文件更简洁，不需要预先知道 QQ 号。QQ 登录会话持久化到 `./napcat/QQ`，重启不丢。Web UI 端口 6099 供管理用。

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add napcat service to docker-compose with health-checked startup"
```

---

### Task 4: 创建 config/napcat.onebot11.json — NapCat 配置模板（裸机用）

**Files:**
- Create: `config/napcat.onebot11.json`

- [ ] **Step 1: 创建配置模板**

```json
{
    "enableWsReverse": true,
    "wsReverseUrls": ["ws://{HOST}:{PORT}/onebot/v11/ws"],
    "enableHttp": false,
    "enableWs": false,
    "messagePostFormat": "array",
    "heartInterval": 30000,
    "token": "",
    "debug": false
}
```

> **说明：** `{HOST}` 和 `{PORT}` 由 `install.sh` 在写入时替换。配置文件名按 NapCat 惯例应在部署时重命名为 `onebot11_<QQ号>.json`，脚本会处理。

- [ ] **Step 2: Commit**

```bash
git add config/napcat.onebot11.json
git commit -m "feat: add napcat onebot11 config template for bare-metal"
```

---

### Task 5: 创建 .gitignore 条目 — 排除 napcat 运行时目录

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: 在 .gitignore 末尾加 napcat 相关条目**

Read `.gitignore`，在末尾追加：
```
# NapCat runtime data
napcat/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore napcat/ runtime directory"
```

---

### Task 6: 修改 .env.example — 加 ONEBOT_WS_PORT

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: 在 .env.example 末尾加可选变量**

在 `.env.example` 末尾追加：
```ini
# OneBot WebSocket 端口（可选，默认 8989）
ONEBOT_WS_PORT=8989
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "feat: add ONEBOT_WS_PORT to .env.example"
```

---

### Task 7: 删除 scripts/install-service.sh

**Files:**
- Delete: `scripts/install-service.sh`

- [ ] **Step 1: 删除旧脚本**

```bash
git rm scripts/install-service.sh
```

- [ ] **Step 2: Commit**

```bash
git commit -m "refactor: remove old install-service.sh, superseded by install.sh"
```

---

### Task 8: 创建 scripts/install.sh — 裸机一键安装脚本

**Files:**
- Create: `scripts/install.sh`

- [ ] **Step 1: 创建完整的 install.sh**

```bash
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

    # NapCat release 下载（注：URL 以实际 release 页面为准）
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
```

- [ ] **Step 2: 给脚本加执行权限**

```bash
chmod +x scripts/install.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/install.sh
git commit -m "feat: add one-click install script for napcat + nonebot bare-metal deployment"
```

---

### Task 9: 最终验证

- [ ] **Step 1: 检查所有变更文件**

```bash
git status
git diff --stat HEAD~8
```

确认变更清单：
- `bot.py` — dotenv 加载
- `Dockerfile` — HEALTHCHECK
- `docker-compose.yml` — napcat 服务
- `config/napcat.onebot11.json` — 配置模板
- `.env.example` — ONEBOT_WS_PORT
- `.gitignore` — napcat/ 排除
- `scripts/install.sh` — 新增
- `scripts/install-service.sh` — 删除

- [ ] **Step 2: 验证 bot.py 能正常加载**

```bash
cd E:/DOCUMENT/WORK/project/simpleQQbot
python -c "import ast; ast.parse(open('bot.py').read()); print('bot.py syntax OK')"
```

- [ ] **Step 3: 验证 docker-compose 格式**

```bash
docker compose config --dry-run 2>/dev/null || echo "Docker not available, skip"
```

- [ ] **Step 4: 验证 install.sh 语法**

```bash
bash -n scripts/install.sh && echo "install.sh syntax OK"
```
