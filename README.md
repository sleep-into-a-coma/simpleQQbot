# QQBot AI

基于 [NoneBot2](https://github.com/nonebot/nonebot2) 的 QQ 群聊 AI Bot，支持多模型、多人格、图片识别、联网搜索。

## 功能

- **多模型支持** — 同时挂载多个 AI 模型（OpenAI 兼容 / Anthropic），按 `/A` `/B` 前缀即时切换
- **多人格系统** — 可配置多种 Bot 人格，支持按群/按用户绑定
- **图片识别** — 接收图片自动调用 Vision 模型描述，非 Vision 模型自动降级
- **联网搜索** — 通过 DuckDuckGo 实现 Tool Calling 联网检索，自动附带来源链接
- **对话记忆** — 基于 SQLite 的上下文对话历史，按 (群, 用户) 隔离
- **权限控制** — 白名单 + 动态 allow/ban 管理
- **频率限制** — 按用户和群维度的消息频率控制
- **错误反馈** — API 异常自动捕获并返回中文错误提示（含错误码、原因、建议）

## 快速开始

### 环境要求

- Python >= 3.11
- 可访问 QQ 的 [go-cqhttp](https://docs.go-cqhttp.org/) 或其他 OneBot v11 兼容客户端

### 安装

```bash
git clone <repo-url>
cd p1
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### 配置

```bash
cp .env.example .env
```

编辑 `.env`，配置模型和 API 密钥（至少配置一个模型和 `DEFAULT_MODEL`）：

| 变量 | 说明 |
|------|------|
| `DEFAULT_MODEL` | 默认使用的模型字母 |
| `MODEL_<ID>_NAME` | 模型名称（如 `deepseek-chat`） |
| `MODEL_<ID>_PROVIDER` | 服务商：`openai_compat` 或 `anthropic` |
| `MODEL_<ID>_API_KEY` | API 密钥 |
| `MODEL_<ID>_API_BASE` | API 地址（OpenAI 兼容时必填） |
| `MODEL_<ID>_VISION` | 是否支持图片（`true` / `false`） |
| `VISION_FALLBACK_*` | 图片降级模型（必填，共 3 项） |
| `SEARCH_ENABLED` | 是否启用搜索（`true` / `false`） |
| `SEARCH_MAX_RESULTS` | 搜索返回条数（默认 5） |

人格配置在 `config/personalities.yaml`，权限白名单和私聊开关在 `config/permissions.yaml`。

### 运行

```bash
python bot.py
```

Bot 启动后将通过 OneBot 反向 WebSocket 连接 go-cqhttp。

## 指令列表

| 指令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/models` | 列出可用模型 |
| `/model <字母>` | 切换当前对话的 AI 模型 |
| `/A <消息>` `/B <消息>` | 临时使用指定模型回复本条消息 |
| `/set <人格名>` | 切换 Bot 人格 |
| `/status` | 查看当前配置和频率使用量 |
| `/summarize` | 总结当前对话历史 |
| `/clear` | 清除对话记忆 |
| `/allow @某人` | 允许某人使用 Bot（管理员） |
| `/ban @某人` | 禁止某人使用 Bot（管理员） |
| `/hire <群号>` | 授权群使用 Bot（管理员） |
| `/fire <群号>` | 撤销群使用权限（管理员） |
| `/allow-p @某人` | 授权某人私聊 Bot（管理员） |
| `/ban-p @某人` | 撤销某人私聊权限（管理员） |
| `/private on/off` | 全局私聊开关（管理员） |
| `/admin` | 查看管理面板（管理员） |

## 错误码

当 AI API 调用失败时，Bot 会返回格式化的错误信息：

```
[E01] 服务响应超时，请稍后重试
📋 可能原因：...
💡 建议操作：...
```

| 错误码 | 含义 |
|--------|------|
| E01 | API 响应超时 |
| E02 | API 鉴权失败（密钥无效/过期） |
| E03 | API 频率限制或额度耗尽 |
| E04 | API 服务器 5xx 错误 |
| E05 | 网络连接失败 |
| E06 | 搜索功能不可用 |
| E07 | 图片下载失败 |
| E08 | 未分类异常 |

## 项目结构

```
p1/
├── bot.py                  # 入口
├── config/
│   ├── personalities.yaml  # 人格定义
│   └── permissions.yaml    # 权限白名单
├── lib/
│   ├── ai_core.py          # AI 处理主流程
│   ├── config.py           # 配置加载
│   ├── context.py          # 对话记忆
│   ├── db.py               # SQLite 数据库
│   ├── errors.py           # 错误码与异常定义
│   ├── model_binding.py    # 模型绑定
│   ├── permission.py       # 权限与频率控制
│   ├── personality.py      # 人格管理
│   ├── models/
│   │   ├── base.py         # 抽象基类
│   │   ├── factory.py      # 客户端工厂
│   │   ├── openai_compat.py
│   │   └── anthropic.py
│   └── tools/
│       └── search.py       # DuckDuckGo 搜索
├── src/plugins/chat/
│   ├── __init__.py         # 插件注册
│   ├── handlers.py         # 命令处理器
│   └── router.py           # 消息路由
└── tests/
    ├── conftest.py
    ├── test_context.py
    └── test_injection_defense.py
```

## 运行测试

```bash
pip install -e ".[dev]"
pytest
```

## 部署

项目包含 Dockerfile 和 docker-compose.yml：

```bash
docker compose up -d
```

首次部署前需准备 `.env` 和 `config/` 目录下的配置文件。
