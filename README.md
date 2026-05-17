# QQBot AI

基于 [NoneBot2](https://github.com/nonebot/nonebot2) 的 QQ 群聊 AI Bot，支持多模型、多人格、图片识别、联网搜索、思维链回显。

## 功能

- **多模型** — 同时挂载多个 AI 模型（OpenAI / Anthropic / DeepSeek 等），`/A` `/B` 即时切换
- **多人格** — 可配置多种 Bot 性格（助手/猫娘/技术顾问等），按群或按用户绑定
- **图片识别** — 发图自动调 Vision 模型描述；非 Vision 模型自动降级
- **联网搜索** — DuckDuckGo Tool Calling，回复自带来源链接
- **对话记忆** — SQLite 上下文记忆，群聊全群共享、私聊按用户隔离
- **权限控制** — 静态白名单 + 动态 allow/ban/hire/fire + 私聊开关
- **频率限制** — 用户/群双维度限流
- **思维链** — `/think on` 显示 AI 推理过程，`<think>` 单次触发
- **用户命名** — `/register 名字` 让 AI 用名字称呼你
- **错误反馈** — API 异常返回中文错误码 + 原因 + 建议

---

## 环境要求

| 项目 | 要求 |
|------|------|
| Python | `>= 3.11`（3.11 / 3.12 / 3.13 均可） |
| QQ 客户端 | 任意 OneBot v11 兼容客户端，例如 [Lagrange](https://github.com/LagrangeDev/Lagrange.Core)、[NapCat](https://github.com/NapNeko/NapCatQQ)、[LLOneBot](https://github.com/LLOneBot/LLOneBot) |
| 网络 | 能访问所选 AI 模型的 API 地址 |
| 操作系统 | Windows 10+ / Linux（Ubuntu/Debian/CentOS） |

> **什么是 OneBot？** QQ 官方不允许机器人直接登录，OneBot 是一个协议标准，它让第三方客户端模拟 QQ 登录，把你的 Bot 程序连接到 QQ。你只需要装一个 OneBot 客户端（如 Lagrange），用你的 QQ 小号扫码登录，Bot 就能收发消息。

---

## Windows 部署（从零开始）

> 以下每一步都有截图级别的详细说明。**不要跳步。**

### 第 1 步：安装 Python

1. 浏览器打开 https://www.python.org/downloads/
2. 点击黄色大按钮下载最新 Python 3.11+ 安装包
3. **关键：** 运行安装包，**第一屏勾选底部的 "Add Python to PATH"**（必须勾，不然后面所有命令都会报"找不到 python"）
4. 点击 "Install Now"，等待完成
5. 验证：按 `Win+R`，输入 `cmd` 回车，在黑窗口输入：

```
python --version
```

如果显示 `Python 3.11.x` 或更高版本号 → 成功。如果显示"不是内部命令"→ 第 3 步没勾 Add to PATH，重装。

### 第 2 步：下载项目

1. 打开项目 GitHub 页面
2. 点击绿色 "Code" 按钮 → "Download ZIP"
3. 把 ZIP 解压到一个你不会搞丢的目录，例如 `D:\qqbot`
4. 解压后你会看到 `bot.py`、`pyproject.toml`、`config` 文件夹等
5. 打开文件资源管理器，在地址栏输入 `cmd` 回车 — 会在当前目录打开命令行

### 第 3 步：创建虚拟环境

> 虚拟环境把 Python 依赖装在这个项目文件夹里，不影响系统其他程序。

在刚刚打开的 cmd 窗口中逐条执行：

```
python -m venv .venv
```

等它完成（无输出就是正常），然后激活：

```
.venv\Scripts\activate
```

激活成功后，命令行的最左边会出现 `(.venv)` 字样。**之后每次重新打开 cmd 操作项目，都要先执行上面这行激活命令。**

### 第 4 步：安装依赖

```
pip install -e .
```

> 如果报错 `pip 不是内部命令` → 虚拟环境没激活，回到第 3 步激活。
> 如果报 `Microsoft Visual C++ 14.0 is required` → 去 https://visualstudio.microsoft.com/visual-cpp-build-tools/ 下载 Build Tools，安装时勾选" C++ 生成工具"，装完重试。

等它跑完（一堆下载进度条），出现 `Successfully installed` 即成功。

### 第 5 步：配置 .env

```
copy .env.example .env
```

然后用记事本打开 `.env`，**至少**填下面几项（每行一个 `= 号后贴你的真实值`）：

```ini
# 必填：模型 A（你的主力模型）
DEFAULT_MODEL=A
MODEL_A_NAME=deepseek-chat
MODEL_A_PROVIDER=openai_compat
MODEL_A_API_BASE=https://api.deepseek.com/v1
MODEL_A_API_KEY=sk-你的真实key

# 必填：Vision 降级模型（不想配也随便填一个）
VISION_FALLBACK_NAME=gpt-4o-mini
VISION_FALLBACK_PROVIDER=openai_compat
VISION_FALLBACK_API_BASE=https://api.openai.com/v1
VISION_FALLBACK_API_KEY=sk-你的真实key
```

**什么是 API Key？** 你去 AI 服务商的网站（DeepSeek、OpenAI 等）注册账号，在控制台/API 管理页面会给你一个 `sk-` 开头的密钥。把这个密钥填到 `MODEL_A_API_KEY=` 后面。

> **怎么获得 DeepSeek API Key？** 打开 https://platform.deepseek.com → 注册登录 → 顶部导航"API Keys"→ 创建新 Key → 复制。

**什么是 API Base？** API 的网址入口。常见服务商：

| 服务商 | API Base |
|--------|----------|
| DeepSeek | `https://api.deepseek.com/v1` |
| OpenAI | `https://api.openai.com/v1` |
| 硅基流动 | `https://api.siliconflow.cn/v1` |
| 阿里百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |

### 第 6 步：配置权限

用记事本打开 `config\permissions.yaml`：

```yaml
admins:
  - "你的QQ号"       # ← 填你的 QQ 号（字符串，加引号）

whitelist:
  users: []           # 留空 = 不限制谁能用
  groups: []           # 留空 = 不限制哪个群能用
```

**管理员 QQ 号填了才能用管理指令。**

### 第 7 步：启动 OneBot 客户端

以 Lagrange 为例：

1. 从 https://github.com/LagrangeDev/Lagrange.Core/releases 下载最新 `Lagrange.OneBot.exe`
2. 双击运行，会生成 `appsettings.json`
3. 关闭它，用记事本打开 `appsettings.json`，找到这部分，改成：

```json
{
    "Implementations": [
        {
            "Type": "ReverseWebSocket",
            "Host": "127.0.0.1",
            "Port": 8989,
            "Suffix": "/onebot/v11/ws",
            "HeartBeatInterval": 5000,
            "AccessToken": ""
        }
    ]
}
```

> **关键：** `Port` 必须是 `8989`，`Suffix` 必须是 `/onebot/v11/ws`，和 Bot 的默认配置一致。

4. 保存，重新双击 `Lagrange.OneBot.exe`
5. 终端会显示一个二维码链接，复制链接用浏览器打开，用**你的 QQ 小号**扫码登录
6. 看到 `Bot Online` 或 `Connected` 即成功

### 第 8 步：启动 Bot

回到项目目录的 cmd（确保 `(.venv)` 在左边）：

```
python bot.py
```

看到类似输出即成功：

```
[INFO] nonebot | Running NoneBot...
[INFO] nonebot | Loaded adapters: OneBot V11
```

### 第 9 步：测试

用另一个 QQ 号（不是 Bot 登录的那个号）在群里或私聊 Bot 发一条消息，Bot 回复了 → 部署完成。

---

## Linux 部署（从零开始）

> 以 Ubuntu 22.04/24.04 为例。Debian 同理。CentOS 把 `apt` 换成 `yum`。

### 第 1 步：安装 Python 3.11+

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git -y
```

验证：

```bash
python3 --version
```

显示 `Python 3.11.x` 或更高 → 成功。如果不是 3.11+，需要加 deadsnakes PPA：

```bash
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.11 python3.11-venv -y
```

### 第 2 步：下载项目

```bash
git clone https://github.com/sleep-into-a-coma/simpleQQbot.git
cd simpleQQbot
```

### 第 3 步：创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

激活后左边出现 `(.venv)`。**以后每次 SSH 进来操作都要 `source .venv/bin/activate`。**

### 第 4 步：安装依赖

```bash
pip install -e .
```

### 第 5 步：配置 .env

```bash
cp .env.example .env
nano .env
```

至少填 `MODEL_A_NAME`、`MODEL_A_PROVIDER`、`MODEL_A_API_BASE`、`MODEL_A_API_KEY`、`VISION_FALLBACK_*`。（参考上方 Windows 第 5 步的说明）

`Ctrl+O` 保存，`Ctrl+X` 退出。

### 第 6 步：配置权限

```bash
nano config/permissions.yaml
```

把你的 QQ 号填入 `admins` 列表（参考上方 Windows 第 6 步）。

### 第 7 步：安装 OneBot 客户端（Lagrange）

```bash
# 下载 Lagrange（替换为最新版本号）
wget https://github.com/LagrangeDev/Lagrange.Core/releases/latest/download/Lagrange.OneBot-linux-x64.tar.gz
mkdir lagrange && tar -xzf Lagrange.OneBot-linux-x64.tar.gz -C lagrange
cd lagrange
```

编辑 `appsettings.json`：

```bash
nano appsettings.json
```

填入：

```json
{
    "Implementations": [
        {
            "Type": "ReverseWebSocket",
            "Host": "127.0.0.1",
            "Port": 8989,
            "Suffix": "/onebot/v11/ws",
            "HeartBeatInterval": 5000,
            "AccessToken": ""
        }
    ]
}
```

### 第 8 步：启动（使用 screen）

> `screen` 让你关掉 SSH 后程序继续跑。没有就装：`sudo apt install screen -y`

开两个 screen 窗口：

**窗口 1 — OneBot 客户端：**

```bash
screen -S lagrange
cd ~/simpleQQbot/lagrange
chmod +x ./Lagrange.OneBot
./Lagrange.OneBot
```

看到二维码链接后用手机 QQ 小号扫码登录。然后 `Ctrl+A D` 分离。

**窗口 2 — Bot：**

```bash
screen -S bot
cd ~/simpleQQbot
source .venv/bin/activate
python bot.py
```

`Ctrl+A D` 分离。

> **恢复查看：** `screen -r lagrange` 或 `screen -r bot`
> **完全退出 screen：** 在 screen 内 `Ctrl+C` 停掉程序，再输入 `exit`

---

## .env 完整配置参考

```ini
# === 必填：默认模型 ===
DEFAULT_MODEL=A

# === 模型 A（示例：DeepSeek）===
MODEL_A_NAME=deepseek-chat
MODEL_A_PROVIDER=openai_compat
MODEL_A_API_BASE=https://api.deepseek.com/v1
MODEL_A_API_KEY=sk-your-deepseek-key
MODEL_A_VISION=false

# === 模型 B（示例：GPT-4o，支持图片）===
MODEL_B_NAME=gpt-4o
MODEL_B_PROVIDER=openai_compat
MODEL_B_API_BASE=https://api.openai.com/v1
MODEL_B_API_KEY=sk-your-openai-key
MODEL_B_VISION=true

# === 模型 C（示例：Claude，支持图片）===
MODEL_C_NAME=claude-sonnet-4-20250514
MODEL_C_PROVIDER=anthropic
MODEL_C_API_KEY=sk-ant-your-anthropic-key
MODEL_C_VISION=true

# === 必填：Vision 降级（无 Vision 能力的模型遇到图片时自动切换到它）===
VISION_FALLBACK_NAME=gpt-4o-mini
VISION_FALLBACK_PROVIDER=openai_compat
VISION_FALLBACK_API_BASE=https://api.openai.com/v1
VISION_FALLBACK_API_KEY=sk-your-key

# === 可选：搜索 ===
SEARCH_ENABLED=true
SEARCH_MAX_RESULTS=5
```

| 变量 | 说明 |
|------|------|
| `DEFAULT_MODEL` | 默认模型字母，必须是下方配置的某个 `MODEL_<ID>` 的 `<ID>` |
| `MODEL_<ID>_NAME` | 模型名，如 `deepseek-chat`、`gpt-4o`、`claude-sonnet-4-20250514` |
| `MODEL_<ID>_PROVIDER` | `openai_compat`（OpenAI/DeepSeek/硅基等）或 `anthropic`（Claude） |
| `MODEL_<ID>_API_BASE` | API 地址。openai_compat 必填，anthropic 可省略 |
| `MODEL_<ID>_API_KEY` | API 密钥 |
| `MODEL_<ID>_VISION` | `true` 或 `false`，是否支持图片识别 |
| `VISION_FALLBACK_NAME` | 图片降级模型名 |
| `VISION_FALLBACK_PROVIDER` | 降级模型服务商 |
| `VISION_FALLBACK_API_BASE` | 降级模型 API 地址 |
| `VISION_FALLBACK_API_KEY` | 降级模型 API 密钥 |
| `SEARCH_ENABLED` | `true` / `false`，是否启用联网搜索 |
| `SEARCH_MAX_RESULTS` | 搜索返回条数，默认 5 |

---

## 权限配置（config/permissions.yaml）

```yaml
# 管理员 QQ 号（可以使用 /allow /ban /hire /fire /private /think /admin 等管理指令）
admins:
  - "你的QQ号"

# 静态白名单（留空 = 不限制）
whitelist:
  users: []       # 允许使用 Bot 的用户 QQ 号
  groups: []      # 允许使用 Bot 的群号

# 频率限制（每分钟）
rate_limit:
  user_per_minute: 10
  group_per_minute: 30

# 私聊开关（可被 /private on/off 指令覆盖）
private_chat:
  enabled: true

# 思维链开关（可被 /think on/off 指令覆盖）
think_enabled: false
```

---

## 人格配置（config/personalities.yaml）

```yaml
default: assistant      # 默认人格

personalities:
  assistant:
    name: 助手模式      # 显示名（当前未使用，仅做注释用）
    system_prompt: "你是一个有帮助的 AI 助手，简洁回答用户问题。"
  catgirl:
    name: 猫娘
    system_prompt: "你是一只可爱的猫娘，说话带喵~尾音。"
  tech_advisor:
    name: 技术顾问
    system_prompt: "你是资深技术专家，回答深入但易懂。"
```

新增人格只需在 `personalities:` 下加一个新 key，写 `system_prompt` 即可。无需修改代码。

---

## 指令列表

| 指令 | 权限 | 说明 |
|------|------|------|
| `/help` | 所有人 | 显示帮助 |
| `/models` | 所有人 | 列出可用模型 |
| `/model <字母>` | 所有人 | 切换当前对话的 AI 模型 |
| `/A <消息>` `/B <消息>` | 所有人 | 临时使用指定模型回复本条 |
| `/set <人格名>` | 所有人 | 切换 Bot 人格 |
| `/status` | 所有人 | 查看当前配置和频率使用量 |
| `/summarize` | 所有人 | 总结当前对话历史 |
| `/clear` | 所有人 | 清除对话记忆 |
| `/register <名称>` | 所有人 | 给自己绑定名称；admin 可 `@某人 名称` 给别人起名 |
| `/Thistory <1/2/3>` | 所有人 | 查看对应槽位的思维链 |
| `/allow @某人` | admin | 允许某人使用 Bot |
| `/ban @某人` | admin | 禁止某人使用 Bot |
| `/hire <群号>` | admin | 授权群使用 Bot |
| `/fire <群号>` | admin | 撤销群使用权限 |
| `/allow-p @某人` | admin | 授权某人私聊 Bot |
| `/ban-p @某人` | admin | 撤销某人私聊权限 |
| `/private on/off` | admin | 全局私聊开关 |
| `/think on/off` | admin | 全局思维链开关 |
| `/admin` | admin | 查看完整管理面板 |

**思维链触发方式：**
- `/think on` → 所有回复带思维链；`/think off` → 关闭
- 消息末尾加 `<think>` → 单次触发，如 `今天天气怎么样<think>`

---

## 错误码

当 AI API 调用失败，Bot 返回：

```
[E01] 服务响应超时，请稍后重试
📋 可能原因：...
💡 建议操作：...
```

| 错误码 | 含义 | 常见处理 |
|--------|------|----------|
| E01 | API 响应超时 | 稍后重试，或换网络 |
| E02 | API 鉴权失败 | 检查 `.env` 中 API Key 是否正确 |
| E03 | API 频率限制/额度耗尽 | 等一等，或去服务商充值 |
| E04 | API 服务器 5xx 错误 | 服务商挂了，等他们恢复 |
| E05 | 网络连接失败 | 检查是否能访问 API 域名 |
| E06 | 搜索功能不可用 | DuckDuckGo 可能限制了你 |
| E07 | 图片下载失败 | 图片链接过期或无法访问 |
| E08 | 未分类异常 | 看具体错误信息排查 |

---

## 常见问题

### Bot 启动了但收不到消息？

1. 确认 OneBot 客户端和 Bot **同时**在运行
2. 确认 OneBot 客户端 `appsettings.json` 的 Port 是 `8989`，Suffix 是 `/onebot/v11/ws`
3. 确认 OneBot 客户端已扫码登录且在线
4. Windows 防火墙可能拦截，尝试临时关闭防火墙测试

### 私聊 Bot 没反应？

1. 检查 `private_chat.enabled` 是否为 `true`
2. 检查是否有 `/ban-p` 禁止了你
3. 检查白名单是否限制了你

### 怎么换 QQ 号登录？

1. 停掉 OneBot 客户端
2. 删除 Lagrange 目录下的 `keystore.json` 或会话文件
3. 重启 OneBot 客户端，用新号扫码

### Linux 后台运行怎么搞？

推荐 `screen` 或 `tmux`（教程见部署步骤）。进阶可以用 `systemd` 守护：

```ini
# /etc/systemd/system/qqbot.service
[Unit]
Description=QQBot AI
After=network.target

[Service]
Type=simple
User=你的用户名
WorkingDirectory=/home/你的用户名/simpleQQbot
ExecStart=/home/你的用户名/simpleQQbot/.venv/bin/python bot.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now qqbot
```

---

## 项目结构

```
simpleQQbot/
├── bot.py                  # 入口文件，python bot.py 启动
├── pyproject.toml          # 项目元数据和依赖声明
├── .env.example            # 环境变量模板（复制为 .env 后编辑）
├── config/
│   ├── personalities.yaml  # 人格定义（增删改都在这里）
│   └── permissions.yaml    # 管理员、白名单、私聊开关、思维链开关
├── lib/
│   ├── ai_core.py          # AI 处理主流程（消息构建+工具调用）
│   ├── config.py           # 配置加载（读 yaml + env）
│   ├── context.py          # 对话记忆存取
│   ├── db.py               # SQLite 建表
│   ├── errors.py           # 错误码与异常
│   ├── model_binding.py    # 模型绑定（按群/用户）
│   ├── permission.py       # 权限、频率控制、思维链、用户命名
│   ├── personality.py      # 人格解析与绑定
│   ├── models/
│   │   ├── base.py         # 抽象基类（ChatMessage/ChatResponse）
│   │   ├── factory.py      # 客户端工厂+缓存
│   │   ├── openai_compat.py # OpenAI 兼容协议
│   │   └── anthropic.py    # Anthropic 协议
│   └── tools/
│       └── search.py       # DuckDuckGo 联网搜索
├── src/plugins/chat/
│   ├── __init__.py         # 插件注册 + 启动初始化
│   ├── handlers.py         # 指令处理（全部 / 命令）
│   └── router.py           # 消息路由（普通消息→AI 处理）
└── tests/
    ├── conftest.py
    ├── test_context.py
    └── test_injection_defense.py
```
