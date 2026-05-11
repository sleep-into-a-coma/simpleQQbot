# QQ Bot AI 聊天机器人设计文档

## 概述

基于 NoneBot2 + NapCatQQ 的 QQ 机器人，接入多模型 AI，支持对话、图片识别、网络搜索、多轮记忆、人格预设、权限控制等功能。部署到 Linux VPS。

## 技术栈

- **框架**: NoneBot2 (Python)
- **QQ 协议端**: NapCatQQ
- **AI**: 多厂商 API（OpenAI 兼容 + Anthropic Claude）
- **存储**: SQLite
- **部署**: Linux VPS（systemd / docker compose）
- **搜索**: DuckDuckGo

## 目录结构

```
p1/
├── bot.py                    # 入口：nb run 启动
├── .env                      # 敏感配置（API Key 等）
├── pyproject.toml
├── config/
│   ├── models.yaml           # 模型列表 & 视觉代理配置
│   ├── personalities.yaml    # 预设人格/System Prompt
│   └── permissions.yaml      # 白名单 & 频率限制默认值
├── src/
│   └── plugins/
│       └── chat/             # NoneBot2 插件包
│           ├── __init__.py   # 消息 handler 注册
│           ├── router.py     # 权限校验 + 频率检查
│           └── handlers.py   # 消息处理入口 → 调用 ai_core
├── lib/                      # 业务逻辑（被插件 import）
│   ├── ai_core.py            # AI 调度核心
│   ├── context.py            # 对话记忆管理
│   ├── permission.py         # 权限逻辑
│   ├── models/
│   │   ├── base.py           # 模型抽象基类
│   │   ├── openai_compat.py  # OpenAI 兼容接口
│   │   └── anthropic.py      # Anthropic Claude
│   ├── tools/
│   │   └── search.py         # DuckDuckGo 搜索工具
│   └── db.py                 # SQLite 初始化 & CRUD 封装
├── data/
│   ├── bot.db                # SQLite 数据库（运行时生成）
│   └── logs/                 # 运行日志
```

## 消息处理流程

```
用户消息
  │
  ▼
┌─────────────┐
│ NoneBot2     │  收到消息事件
│ msg handler  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 权限检查     │  白名单? 封禁? → 拒绝并返回
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 频率限制     │  超限? → 返回提示
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ AI 调度核心  │
│             │
│ 1. 加载记忆  │  从 SQLite 读该 (群,用户) 的历史
│ 2. 图片处理  │  有图片 → 主模型支持视觉? 直接用 : 走视觉代理
│ 3. 构建请求  │  System Prompt + 记忆 + 用户消息 + 工具定义(搜索)
│ 4. 调用模型  │  可能多轮: AI 调搜索 → 注入结果 → 再调 AI
│ 5. 保存记忆  │  存本轮对话到 SQLite
│ 6. 生成元数据│  是否搜索 / 是否识图 / 人格名 / 模型名 / 耗时
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 发送回复     │  正文 + 元数据标注（人格/模型/搜索/识图/耗时） + 来源链接(如有)
└─────────────┘
```

## SQLite 表设计

```sql
-- 对话记忆，按 (群, 用户) 隔离
CREATE TABLE conversation_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,           -- 'user' | 'assistant'（system prompt 来自人格配置，不存储在此）
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 回复元数据日志，用于可视化管理
CREATE TABLE reply_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    personality_name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    has_image BOOLEAN DEFAULT 0,
    has_search BOOLEAN DEFAULT 0,
    response_time_ms INTEGER,
    user_msg TEXT,               -- 用户消息摘要
    reply TEXT,                  -- Bot 回复摘要
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 动态权限
CREATE TABLE permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,    -- 'user' | 'group'
    target_id TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'allow',  -- 'allow' | 'block'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(target_type, target_id)
);

-- 人格绑定
CREATE TABLE personality_bindings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,    -- 'user' | 'group'
    target_id TEXT NOT NULL,
    personality_name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(target_type, target_id)
);
```

## 配置文件

### config/models.yaml

```yaml
default: deepseek-v3

models:
  deepseek-v3:
    provider: openai_compat
    api_base: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
    model: deepseek-chat
    supports_vision: false

  gpt-4o:
    provider: openai_compat
    api_base: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    model: gpt-4o
    supports_vision: true

  claude-3.5-sonnet:
    provider: anthropic
    api_key_env: ANTHROPIC_API_KEY
    model: claude-3-5-sonnet-20241022
    supports_vision: true

vision_fallback:
  provider: openai_compat
  api_base: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
  model: gpt-4o-mini

# 触发式临时切换别名 (如 /A 本条消息临时用 gpt-4o)
aliases:
  A: gpt-4o
  B: deepseek-v3
  C: claude-3.5-sonnet

search:
  enabled: true
  backend: duckduckgo
  max_results: 5
```

### config/personalities.yaml

```yaml
default: assistant

personalities:
  assistant:
    name: 助手模式
    system_prompt: "你是一个有帮助的 AI 助手，简洁回答用户问题。"
  catgirl:
    name: 猫娘
    system_prompt: "你是一只可爱的猫娘，说话带「喵~」尾音..."
  tech_advisor:
    name: 技术顾问
    system_prompt: "你是资深技术专家，回答深入但易懂..."
```

### config/permissions.yaml

```yaml
admins: []    # Bot 管理员 QQ 号，可使用 /allow /ban 等管理指令

whitelist:
  users: []
  groups: []

rate_limit:
  user_per_minute: 10
  group_per_minute: 30
```

## 指令列表

| 指令 | 类型 | 作用 |
|------|------|------|
| `/help` | — | 列出所有可用指令及用法 |
| `/set <人格名>` | 转换式 | 切换当前群/个人的 Bot 人格 |
| `/model <模型名>` | 转换式 | 切换当前群/个人的 AI 模型 |
| `/A` `/B` `/C` 等 | 触发式 | 仅本条消息临时用对应模型回复 |
| `/models` | — | 列出可用模型及触发别名 |
| `/allow @某人 / 群号` | — | 允许某人/群使用 Bot（需管理员权限） |
| `/ban @某人 / 群号` | — | 禁止某人/群使用 Bot（需管理员权限） |
| `/clear` | — | 清除当前对话记忆 |
| `/status` | — | 查看当前配置（人格、模型、频率用量） |

## 功能模块

### 1. 多模型切换

两种切换方式：

**转换式（持久切换）：**
- `/model <模型名>` 切换当前对话的默认模型，之后所有消息使用新模型
- 切换范围按 (群, 用户)，持久生效

**触发式（临时切换）：**
- `/A` `/B` `/C` 等别名，仅对当前这一条消息使用对应模型
- 回复完自动恢复默认模型，不改变持久设置
- 别名映射在 `config/models.yaml` 的 `aliases` 中定义

- 配置定义模型列表，每个模型标注 provider、endpoint、是否支持视觉
- 默认模型通过 `config/models.yaml` 的 `default` 指定
- `/models` 查看所有可用模型

### 2. 图片识别（视觉代理）

- 主模型支持视觉 → 图片直接发送给主模型
- 主模型不支持视觉 → 先用 `vision_fallback` 模型将图片转为文字描述，描述注入用户消息，再发给主模型

### 3. 网络搜索

- 搜索以 AI 工具调用方式实现：定义 search 工具函数签名，AI 自行决定何时调用
- 后端使用 DuckDuckGo，免费无需 API Key
- 搜索结果注入上下文后再调 AI 总结
- 回复末尾附带搜索结果来源链接

### 4. 回复元数据

- 每次回复末尾标注：`🔍搜索 | 🖼识图 | <人格名> | <模型名> | <耗时>s`
- 同时写入 `reply_log` 表，包含完整元数据
- 用于后续可视化管理面板

### 5. 对话记忆

- 按 (group_id, user_id) 隔离，每个组合保留最近 20 轮对话
- 存储时分条写入 `conversation_memory`，读取时按时间排序取最近 20 轮
- System Prompt 来自人格配置，不存储在记忆表中
- `/clear` 清除当前对话记忆

### 6. 预设人格

- 默认人格通过 `config/personalities.yaml` 的 `default` 指定
- `/set` 指令切换，可按 (群, 用户) 绑定不同人格
- 人格绑定持久化到 `personality_bindings` 表

### 7. 权限控制

- 静态规则：`config/permissions.yaml` 中的白名单
- 动态规则：通过 `/allow` `/ban` 指令管理，存入 `permissions` 表
- `/allow` `/ban` 仅 Bot 管理员可用（管理员 QQ 号在配置文件中定义）
- 权限判断：动态规则优先于静态规则，block 优先于 allow

### 8. 频率限制

- 用户维度：每个用户每分钟最大消息数
- 群维度：每个群每分钟最大总消息数
- 默认值在 `config/permissions.yaml`，运行时在内存中追踪计数

## 部署

```
# VPS 上安装
pip install nonebot2 nb-cli

# 配置 .env 文件（API Key）
# 启动 NapCatQQ（QQ 协议端）
# 启动 NoneBot2
nb run

# 进程守护：systemd 或 docker compose
```
