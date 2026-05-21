# One-Click Deployment Packages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a build system (`simpleQQbot-dist/`) that generates 4 distribution packages from source, plus rewrite the README for one-click deployment UX.

**Architecture:** `build.sh` rsyncs source from `../simpleQQbot/` into a temp `build/` dir, prunes dev files, injects platform-specific scripts and vendor deps, then zips/tars into `artifacts/`. Windows uses `.bat` entry scripts; Linux uses an enhanced `install.sh` with `--offline` support.

**Tech Stack:** Bash (build script + Linux installer), Windows Batch (start.bat/setup.bat), Python pip download (for offline wheels)

**Files to create:**
- `../simpleQQbot-dist/.gitignore`
- `../simpleQQbot-dist/build.sh`
- `../simpleQQbot-dist/patch/windows/start.bat`
- `../simpleQQbot-dist/patch/windows/setup.bat`
- `../simpleQQbot-dist/patch/windows/README.md`

**Files to modify:**
- `scripts/install.sh` — add `--offline` flag
- `README.md` — complete rewrite

---

### Task 1: Enhance install.sh with --offline support

**Files:**
- Modify: `scripts/install.sh`

- [ ] **Step 1: Add --offline flag parsing at the top of main()**

In `main()`, after `cd "$PROJECT_DIR"`, add argument parsing:

```bash
OFFLINE=false
if [ "${1:-}" = "--offline" ]; then
    OFFLINE=true
fi
```

- [ ] **Step 2: Skip system deps install when offline**

Change `install_system_deps` call in `main()` from unconditional to conditional:

```bash
if $OFFLINE; then
    log_info "离线模式：跳过系统依赖安装（请确保 python3 已安装）"
else
    detect_os
    install_system_deps
fi
```

Note: `detect_os` only runs in online mode; offline mode skips it entirely.

- [ ] **Step 3: Add offline branch to setup_venv()**

```bash
setup_venv() {
    log_info "创建Python虚拟环境..."
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    source .venv/bin/activate
    if $OFFLINE && [ -d "wheels" ]; then
        log_info "离线模式：从 wheels/ 安装依赖..."
        pip install --no-index --find-links=wheels/ -e .
    else
        pip install -e .
    fi
    log_info "Python依赖安装完成"
}
```

- [ ] **Step 4: Add offline branch to install_napcat()**

```bash
install_napcat() {
    NAPCAT_DIR="$HOME/napcat"
    if [ -d "$NAPCAT_DIR" ] && [ -f "$NAPCAT_DIR/napcat" ]; then
        log_info "NapCat 已安装，跳过"
        return
    fi

    if $OFFLINE; then
        log_info "离线模式：从本地安装 NapCat..."
        ARCH=$(uname -m)
        case "$ARCH" in
            x86_64)  NAPCAT_ARCH="amd64";;
            aarch64) NAPCAT_ARCH="arm64";;
            *)
                log_error "不支持的CPU架构: $ARCH"
                exit 1
                ;;
        esac
        NAPCAT_TARBALL="napcat/napcat-linux-${NAPCAT_ARCH}.tar.gz"
        if [ ! -f "$NAPCAT_TARBALL" ]; then
            log_error "未找到 $NAPCAT_TARBALL，离线安装失败"
            log_error "请确保完整包已正确解压"
            exit 1
        fi
        mkdir -p "$NAPCAT_DIR"
        tar -xzf "$NAPCAT_TARBALL" -C "$NAPCAT_DIR"
        chmod +x "$NAPCAT_DIR/napcat"
        log_info "NapCat 安装完成: $NAPCAT_DIR"
        return
    fi

    # ... existing online download logic unchanged ...
}
```

Insert the offline branch before the existing `log_info "下载 NapCat..."` line. The existing online path remains intact after the `if $OFFLINE` block.

> **Important:** When inserting, place the offline block right after the `if [ -d "$NAPCAT_DIR" ]` check (the early-return for already-installed), and before `log_info "下载 NapCat..."`. The full online download code after `return`/`fi` stays as-is.

- [ ] **Step 5: Run bash syntax check**

```bash
bash -n scripts/install.sh
```

Expected: no output (no syntax errors).

- [ ] **Step 6: Commit**

```bash
git add scripts/install.sh
git commit -m "feat: add --offline mode to install.sh for bundled deployment"
```

---

### Task 2: Create simpleQQbot-dist directory and .gitignore

**Files:**
- Create: `../simpleQQbot-dist/.gitignore`

- [ ] **Step 1: Create directory**

```bash
mkdir -p ../simpleQQbot-dist/patch/windows
mkdir -p ../simpleQQbot-dist/artifacts
mkdir -p ../simpleQQbot-dist/vendor
```

- [ ] **Step 2: Write .gitignore**

```gitignore
# Generated packages
artifacts/

# Downloaded at build time, not committed
vendor/python-embed/
vendor/get-pip.py

# Build temp
build/
```

- [ ] **Step 3: Verify directory structure**

```bash
ls -la ../simpleQQbot-dist/
```

Expected: `.gitignore`, `artifacts/`, `patch/`, `vendor/`.

- [ ] **Step 4: Commit**

```bash
git -C ../simpleQQbot-dist init
git -C ../simpleQQbot-dist add -A
git -C ../simpleQQbot-dist commit -m "chore: init packaging workspace"
```

---

### Task 3: Write Windows start.bat

**Files:**
- Create: `../simpleQQbot-dist/patch/windows/start.bat`

- [ ] **Step 1: Write start.bat**

```batch
@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   QQBot AI - 启动脚本
echo ========================================
echo.

:: Step 1: Check .env
if not exist ".env" (
    echo [错误] 未找到 .env 文件
    echo 请先复制 .env.example 为 .env 并填写配置
    echo.
    echo 正在打开 .env.example 供你编辑...
    start notepad .env.example
    echo.
    echo 编辑完成后保存为 .env，再重新运行 start.bat
    pause
    exit /b 1
)

:: Step 2: Check venv
if not exist ".venv\Scripts\python.exe" (
    echo [提示] 虚拟环境未创建，正在运行 setup.bat...
    call setup.bat
    if errorlevel 1 (
        echo [错误] setup.bat 执行失败
        pause
        exit /b 1
    )
)

:: Step 3: Check NapCat
set NAPCAT_FOUND=0
if exist "napcat\napcat.exe" (
    set NAPCAT_FOUND=1
)

if !NAPCAT_FOUND!==1 (
    echo [提示] 检测到内置 NapCat，将自动启动
    echo.
    echo 启动 NapCat QQ 客户端...
    start "NapCat" "napcat\napcat.exe"
    timeout /t 2 >nul
) else (
    echo [提示] 未检测到内置 NapCat
    echo 请自行下载 NapCat 并配置反向 WebSocket 连接到 ws://127.0.0.1:8989/onebot/v11/ws
    echo 下载地址: https://github.com/NapNeko/NapCatQQ/releases
    echo.
)

:: Step 4: Start bot
echo.
echo ========================================
echo   启动 QQBot AI...
echo ========================================
echo.
echo 请将 NapCat 扫码登录后即可使用
echo 按 Ctrl+C 停止 Bot
echo.

.venv\Scripts\python.exe bot.py

pause
```

- [ ] **Step 2: Commit**

```bash
git -C ../simpleQQbot-dist add patch/windows/start.bat
git -C ../simpleQQbot-dist commit -m "feat: add Windows start.bat entry script"
```

---

### Task 4: Write Windows setup.bat

**Files:**
- Create: `../simpleQQbot-dist/patch/windows/setup.bat`

- [ ] **Step 1: Write setup.bat**

```batch
@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo   QQBot AI - 环境安装
echo ========================================
echo.

:: Detect embedded Python
set PYTHON_EXE=python
set PIP_INSTALL_ARGS=-e .

if exist "python\python.exe" (
    echo [检测] 自包含包模式 - 使用内嵌 Python
    set PYTHON_EXE=python\python.exe
    
    echo.
    echo [1/3] 创建虚拟环境...
    !PYTHON_EXE! -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        exit /b 1
    )
    
    echo [2/3] 安装 pip...
    .venv\Scripts\python.exe python\get-pip.py --no-index --find-links=wheels\
    if errorlevel 1 (
        echo [错误] pip 安装失败
        exit /b 1
    )
    
    echo [3/3] 安装项目依赖...
    .venv\Scripts\pip.exe install --no-index --find-links=wheels\ -e .
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        exit /b 1
    )
) else (
    echo [检测] 轻量包模式 - 使用系统 Python
    echo.
    
    :: Verify system python
    python --version >nul 2>&1
    if errorlevel 1 (
        echo [错误] 未检测到 Python，请先安装 Python 3.11+
        echo 下载: https://www.python.org/downloads/
        echo 安装时必须勾选 "Add Python to PATH"
        pause
        exit /b 1
    )
    
    echo [1/2] 创建虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        exit /b 1
    )
    
    echo [2/2] 安装项目依赖（联网下载）...
    .venv\Scripts\pip.exe install -e .
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络连接
        exit /b 1
    )
)

echo.
echo ========================================
echo   环境安装完成！
echo ========================================
echo.
```

> **Note:** This detects light vs full by presence of `python\python.exe`. Full pack ships `python/` directory with embedded Python; light pack doesn't.

- [ ] **Step 2: Commit**

```bash
git -C ../simpleQQbot-dist add patch/windows/setup.bat
git -C ../simpleQQbot-dist commit -m "feat: add Windows setup.bat (light + full auto-detect)"
```

---

### Task 5: Write build.sh

**Files:**
- Create: `../simpleQQbot-dist/build.sh`

- [ ] **Step 1: Write build.sh header and common infrastructure**

```bash
#!/usr/bin/env bash
# 打包生成脚本 - 从 ../simpleQQbot 源码生成 4 个发布包
# 用法: bash build.sh [windows-light|windows-full|linux-light|linux-full|all]
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")/simpleQQbot"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

EXCLUDES=(
    --exclude=.git
    --exclude=__pycache__
    --exclude='*.pyc'
    --exclude=.venv
    --exclude=.env
    --exclude='data/*.db'
    --exclude='data/*.db-journal'
    --exclude='data/*.db-wal'
    --exclude=data/logs
    --exclude=.claude
    --exclude=.pytest_cache
    --exclude=.idea
    --exclude=.vscode
    --exclude=release
    --exclude='docs/superpowers'
    --exclude=tests
    --exclude=napcat
    --exclude=.dockerignore
    --exclude=Dockerfile
    --exclude=docker-compose.yml
    --exclude=scripts/install-service.sh
    --exclude=scripts/qqbot.service
)

build_common() {
    log_info "复制源码..."
    rm -rf build
    mkdir -p build/qqbot
    rsync -a "${EXCLUDES[@]}" "$SOURCE_DIR"/ build/qqbot/
    log_info "源码复制完成"
}

download_napcat() {
    local PLATFORM=$1  # windows, linux
    local ARCH=$2      # amd64, arm64
    local DEST=$3      # destination path

    if [ "$PLATFORM" = "windows" ]; then
        local URL="https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.windows-amd64.zip"
    else
        local URL="https://github.com/NapNeko/NapCatQQ/releases/latest/download/NapCat.linux-${ARCH}.tar.gz"
    fi

    log_info "下载 NapCat ($PLATFORM-$ARCH)..."
    mkdir -p "$(dirname "$DEST")"
    wget -q --show-progress "$URL" -O "$DEST" || {
        log_error "NapCat 下载失败: $URL"
        exit 1
    }
}

download_pip_bootstrap() {
    log_info "下载 get-pip.py..."
    wget -q --show-progress https://bootstrap.pypa.io/get-pip.py -O vendor/get-pip.py || {
        log_error "get-pip.py 下载失败"
        exit 1
    }
}

download_python_embed() {
    if [ -d "vendor/python-embed" ] && [ -f "vendor/python-embed/python.exe" ]; then
        log_info "Python embed 已缓存，跳过下载"
        return
    fi
    log_info "下载 Python 3.11 embeddable..."
    mkdir -p vendor/python-embed
    local URL="https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
    wget -q --show-progress "$URL" -O /tmp/python-embed.zip || {
        log_error "Python embed 下载失败"
        exit 1
    }
    unzip -qo /tmp/python-embed.zip -d vendor/python-embed
    rm -f /tmp/python-embed.zip
    # Enable pip in embed: uncomment 'import site' in python311._pth
    sed -i 's/#import site/import site/' vendor/python-embed/python311._pth
    log_info "Python embed 准备完成"
}

download_wheels() {
    log_info "下载 Python 依赖 wheels..."
    mkdir -p vendor/wheels
    pip download \
        --python-version 3.11 \
        --platform win_amd64 \
        --only-binary :all: \
        -d vendor/wheels/ \
        "nonebot2>=2.3.0" \
        "httpx>=0.27.0" \
        "duckduckgo_search>=7.0.0" \
        "pyyaml>=6.0" \
        "aiosqlite>=0.20.0" \
        "python-dotenv>=1.0.0" \
        "nonebot-plugin-localstore>=0.6.0" \
        "nonebot-adapter-onebot>=2.4.0"
    # anthropic is pure Python, no binary constraint needed
    pip download \
        --python-version 3.11 \
        -d vendor/wheels/ \
        "anthropic>=0.39.0"
    log_info "Wheels 下载完成: $(ls vendor/wheels/ | wc -l) 个文件"
}

package_zip() {
    local NAME=$1
    log_info "打包 $NAME.zip..."
    (cd build && zip -qr "../artifacts/$NAME.zip" .)
    log_info "$NAME.zip 生成完成"
}

package_tar() {
    local NAME=$1
    log_info "打包 $NAME.tar.gz..."
    tar -czf "artifacts/$NAME.tar.gz" -C build .
    log_info "$NAME.tar.gz 生成完成"
}
```

- [ ] **Step 2: Write build_windows_light()**

```bash
build_windows_light() {
    log_info "=== 构建 Windows 轻量包 ==="
    build_common
    cp patch/windows/start.bat build/qqbot/
    cp patch/windows/setup.bat build/qqbot/
    cp patch/windows/README.md build/qqbot/
    package_zip qqbot-windows-light
    rm -rf build
}
```

- [ ] **Step 3: Write build_windows_full()**

```bash
build_windows_full() {
    log_info "=== 构建 Windows 自包含包 ==="
    build_common

    # Download vendor deps (cached)
    download_pip_bootstrap
    download_python_embed
    download_wheels

    # Copy scripts
    cp patch/windows/start.bat build/qqbot/
    cp patch/windows/setup.bat build/qqbot/
    cp patch/windows/README.md build/qqbot/

    # Bundle embedded Python
    cp -r vendor/python-embed build/qqbot/python/
    cp vendor/get-pip.py build/qqbot/python/

    # Bundle wheels
    cp -r vendor/wheels build/qqbot/wheels/

    # Bundle NapCat
    download_napcat windows amd64 build/qqbot/napcat/napcat-windows-amd64.zip
    # Extract NapCat for direct use
    unzip -qo build/qqbot/napcat/napcat-windows-amd64.zip -d build/qqbot/napcat/

    package_zip qqbot-windows-full
    rm -rf build
}
```

- [ ] **Step 4: Write build_linux_light()**

```bash
build_linux_light() {
    log_info "=== 构建 Linux 轻量包 ==="
    build_common

    # Copy install.sh from source repo (enhanced version)
    cp "$SOURCE_DIR/scripts/install.sh" build/qqbot/

    package_tar qqbot-linux-light
    rm -rf build
}
```

- [ ] **Step 5: Write build_linux_full()**

```bash
build_linux_full() {
    log_info "=== 构建 Linux 自包含包 ==="
    build_common

    # Copy install.sh (supports --offline)
    cp "$SOURCE_DIR/scripts/install.sh" build/qqbot/

    # Download Linux wheels (pure Python, no platform constraint)
    log_info "下载 Linux Python 依赖 wheels..."
    mkdir -p build/qqbot/wheels
    pip download \
        --python-version 3.11 \
        -d build/qqbot/wheels/ \
        "nonebot2>=2.3.0" \
        "httpx>=0.27.0" \
        "anthropic>=0.39.0" \
        "duckduckgo_search>=7.0.0" \
        "pyyaml>=6.0" \
        "aiosqlite>=0.20.0" \
        "python-dotenv>=1.0.0" \
        "nonebot-plugin-localstore>=0.6.0" \
        "nonebot-adapter-onebot>=2.4.0"
    log_info "Wheels 下载完成: $(ls build/qqbot/wheels/ | wc -l) 个文件"

    # Bundle NapCat (both architectures)
    mkdir -p build/qqbot/napcat
    download_napcat linux amd64 build/qqbot/napcat/napcat-linux-amd64.tar.gz
    download_napcat linux arm64 build/qqbot/napcat/napcat-linux-arm64.tar.gz

    package_tar qqbot-linux-full
    rm -rf build
}
```

- [ ] **Step 6: Write main entry point**

```bash
main() {
    cd "$SCRIPT_DIR"
    mkdir -p artifacts

    case "${1:-}" in
        windows-light)
            build_windows_light
            ;;
        windows-full)
            build_windows_full
            ;;
        linux-light)
            build_linux_light
            ;;
        linux-full)
            build_linux_full
            ;;
        all|"")
            build_windows_light
            build_windows_full
            build_linux_light
            build_linux_full
            ;;
        *)
            echo "用法: bash build.sh [windows-light|windows-full|linux-light|linux-full|all]"
            echo ""
            echo "  windows-light    Windows 轻量包（需自装 Python + NapCat）"
            echo "  windows-full     Windows 自包含包（内嵌所有依赖）"
            echo "  linux-light      Linux 轻量包（需联网）"
            echo "  linux-full       Linux 自包含包（离线可装）"
            echo "  all              生成全部 4 个包（默认）"
            exit 1
            ;;
    esac

    echo ""
    log_info "=== 打包完成 ==="
    ls -lh artifacts/
}

main "$@"
```

- [ ] **Step 7: Make build.sh executable**

```bash
chmod +x ../simpleQQbot-dist/build.sh
```

- [ ] **Step 8: Run bash syntax check**

```bash
bash -n ../simpleQQbot-dist/build.sh
```

Expected: no output.

- [ ] **Step 9: Commit**

```bash
git -C ../simpleQQbot-dist add build.sh
git -C ../simpleQQbot-dist commit -m "feat: add build.sh package generator"
```

---

### Task 6: Write in-package README.md

**Files:**
- Create: `../simpleQQbot-dist/patch/windows/README.md`

- [ ] **Step 1: Write simplified README**

```markdown
# QQBot AI

基于 NoneBot2 的 QQ 群聊 AI Bot。

## 快速启动

### 第一次使用

1. 复制 `.env.example` 为 `.env`
2. 用记事本打开 `.env`，填写你的 API Key 和模型配置
3. 用记事本打开 `config\permissions.yaml`，填写你的 QQ 号到 `admins:`
4. 双击 `start.bat`

### 扫码登录

启动后会有一个 NapCat 窗口显示二维码：
- 如果二维码显示为链接，复制链接用浏览器打开
- 用你的 **QQ 小号** 扫码登录
- 看到 "Bot Online" 即成功

### 测试

用另一个 QQ 号给 Bot 发消息，有回复即部署成功。

## 指令

| 指令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/models` | 列出可用模型 |
| `/A <消息>` | 使用模型 A 回复 |
| `/status` | 查看当前配置 |
| `/set <人格>` | 切换 Bot 人格 |
| `/clear` | 清除对话记忆 |

更多指令和完整文档见 GitHub 仓库。
```

- [ ] **Step 2: Commit**

```bash
git -C ../simpleQQbot-dist add patch/windows/README.md
git -C ../simpleQQbot-dist commit -m "docs: add in-package README for Windows"
```

---

### Task 7: Rewrite main README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the new README**

Read the current README first to preserve config reference, command list, error codes, and FAQ sections. The new README replaces lines 1 through the end of the old Windows manual deployment section (everything up to "## Linux 部署"), with new quick-start content.

The rewritten README sections to replace:

**Section: 简介 + 功能** (keep, trim 功能 bullets to one line each)

**Section: 环境要求** → replace with a simpler table:

```markdown
## 快速开始

### Windows

1. 下载 [qqbot-windows-light.zip](releases) 或 [qqbot-windows-full.zip](releases)
2. 解压到任意目录
3. 复制 `.env.example` 为 `.env`，填写 API Key
4. 双击 `start.bat`

> **自包含包 (full)** 内嵌 Python 和 NapCat，无需预装任何软件。**轻量包 (light)** 需自行安装 Python 3.11+ 和 NapCat。

### Linux

```bash
# 轻量包（需联网）
tar -xzf qqbot-linux-light.tar.gz
cd qqbot
bash install.sh

# 自包含包（可离线）
tar -xzf qqbot-linux-full.tar.gz
cd qqbot
bash install.sh --offline
```

### Docker

```bash
git clone https://github.com/sleep-into-a-coma/simpleQQbot.git
cd simpleQQbot
cp .env.example .env && nano .env
docker compose up -d
```

## 选择哪个包？

| 场景 | 推荐 |
|------|------|
| Windows，想最快启动 | `windows-full` |
| Windows，已有 Python，想最小下载 | `windows-light` |
| Linux，服务器有网 | `linux-light` |
| Linux，离线/内网环境 | `linux-full` |
| 想容器化运行 | Docker Compose |
| 开发者/想改源码 | git clone 手动安装 |
```

**Section: 配置** (preserve the existing `.env` reference, permissions, personalities sections)

**Section: 指令列表** (preserve as-is)

**Section: 错误码** (preserve as-is)

**Section: 常见问题** (update — remove Python/venv troubleshooting, add package-specific Q&A):

```markdown
## 常见问题

### start.bat 闪退？
右键点击 `start.bat` → 编辑，在最后一行前加 `pause`，保存后重新双击，看错误信息。

### "未检测到 Python"
你下载的是轻量包，需要装 Python。去 https://www.python.org/downloads/ 下载，安装时勾选 "Add Python to PATH"。或者改用自包含包。

### Bot 启动了但收不到消息？
1. 确认 NapCat 已扫码登录且在线
2. 确认 NapCat 配置的反向 WebSocket 地址是 `ws://127.0.0.1:8989/onebot/v11/ws`

### 怎么换 QQ 号登录？
删除 NapCat 的会话文件后重启：
- Windows: 删除 `napcat/` 目录下 QQ 号对应的文件夹
- Linux: 删除 `~/napcat/` 下 QQ 号对应的文件夹

### API 调用报错 E02/E05？
- E02: API Key 错误，检查 `.env` 中填的 Key
- E05: 网络不通。如果在国内使用 OpenAI/Anthropic，需要配代理（在 `.env` 中设 `PROXY_URL=http://127.0.0.1:7890`）
```

Then preserve the existing project structure section (updated) and add:

```markdown
## 项目结构

```
qqbot/
├── start.bat / install.sh   # 启动脚本
├── bot.py                    # 入口
├── .env.example              # 配置模板
├── config/                   # 权限 + 人格配置
├── lib/                      # 核心库
│   ├── ai_core.py            # AI 处理流程
│   ├── models/               # 模型客户端
│   └── tools/                # 搜索工具
└── src/plugins/chat/         # NoneBot 插件
```

## 开发

本项目开源在 [GitHub](https://github.com/sleep-into-a-coma/simpleQQbot)。

```bash
git clone https://github.com/sleep-into-a-coma/simpleQQbot.git
cd simpleQQbot
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Linux
pip install -e .[dev]
python bot.py
```
```

- [ ] **Step 2: Verify the new README reads coherently end-to-end**

Read the file from top to bottom. Check that:
- No broken references to deleted sections
- Config section links still work (`.env` reference table preserved)
- Command list and error codes are intact

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for one-click package deployment"
```

---

### Task 8: End-to-end verification

- [ ] **Step 1: Run build.sh all**

```bash
cd ../simpleQQbot-dist && bash build.sh all
```

Expected: 4 files in `artifacts/`:
```
qqbot-windows-light.zip
qqbot-windows-full.zip
qqbot-linux-light.tar.gz
qqbot-linux-full.tar.gz
```

- [ ] **Step 2: Inspect windows-light.zip contents**

```bash
unzip -l artifacts/qqbot-windows-light.zip
```

Verify:
- `start.bat` and `setup.bat` present at root
- No `.git`, `__pycache__`, `.venv`, `tests/`, docs/superpowers present
- `.env.example` present, `.env` absent
- `config/`, `lib/`, `src/` present

- [ ] **Step 3: Inspect windows-full.zip contents**

```bash
unzip -l artifacts/qqbot-windows-full.zip
```

Verify all of light checks plus:
- `python/` directory with `python.exe` and `get-pip.py`
- `wheels/` directory with .whl files
- `napcat/` directory with `napcat.exe`

- [ ] **Step 4: Inspect linux-light.tar.gz contents**

```bash
tar -tzf artifacts/qqbot-linux-light.tar.gz
```

Verify:
- `install.sh` present
- No dev files
- No `wheels/` or `napcat/` directory

- [ ] **Step 5: Inspect linux-full.tar.gz contents**

```bash
tar -tzf artifacts/qqbot-linux-full.tar.gz
```

Verify:
- `install.sh` present
- `wheels/` directory with .whl files
- `napcat/` directory with both `napcat-linux-amd64.tar.gz` and `napcat-linux-arm64.tar.gz`

- [ ] **Step 6: Test install.sh --offline syntax**

```bash
# Extract linux-full to temp, run bash -n on install.sh
tar -xzf artifacts/qqbot-linux-full.tar.gz -C /tmp/qqbot-test
bash -n /tmp/qqbot-test/qqbot/install.sh
rm -rf /tmp/qqbot-test
```

Expected: no syntax errors.

- [ ] **Step 7: Commit any final adjustments**

```bash
git -C ../simpleQQbot-dist add -A
git -C ../simpleQQbot-dist commit -m "chore: final adjustments from verification"
```
