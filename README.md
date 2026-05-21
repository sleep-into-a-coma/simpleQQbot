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

## 快速开始

### Windows

1. 下载 [qqbot-windows-light.zip](https://github.com/sleep-into-a-coma/simpleQQbot/releases) 或 [qqbot-windows-full.zip](https://github.com/sleep-into-a-coma/simpleQQbot/releases)
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

---

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
