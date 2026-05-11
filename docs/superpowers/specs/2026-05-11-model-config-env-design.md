# Model Config Migration to .env

## 概述

将模型配置从 `config/models.yaml` 迁移到 `.env`，模型标识符从长名称（`deepseek-v3`）改为大写字母（`A`），统一 `/model A`（持久切换）和 `/A`（临时切换）的用户接口。

## 动机

- **单一配置源**：所有可部署配置集中在 `.env`，Docker/CI 友好
- **简化概念**：字母即是模型名，不再区分 `name` 和 `aliases`
- **直接配置**：每个模型的 API key 直接写在模型配置中，无需间接引用 env 变量名，方便自定义 provider

## .env 格式

```env
# 默认模型（必须指向一个配置了的模型字母）
DEFAULT_MODEL=A

# 模型 A
MODEL_A_NAME=deepseek-chat
MODEL_A_PROVIDER=openai_compat
MODEL_A_API_BASE=https://api.deepseek.com/v1
MODEL_A_API_KEY=sk-xxx
MODEL_A_VISION=false

# 模型 B
MODEL_B_NAME=gpt-4o
MODEL_B_PROVIDER=openai_compat
MODEL_B_API_BASE=https://api.openai.com/v1
MODEL_B_API_KEY=sk-xxx
MODEL_B_VISION=true

# 模型 C
MODEL_C_NAME=claude-3-5-sonnet-20241022
MODEL_C_PROVIDER=anthropic
MODEL_C_API_KEY=sk-ant-xxx
MODEL_C_VISION=true

# Vision 降级（独立配置，可指向不暴露给用户的模型）
VISION_FALLBACK_NAME=gpt-4o-mini
VISION_FALLBACK_PROVIDER=openai_compat
VISION_FALLBACK_API_BASE=https://api.openai.com/v1
VISION_FALLBACK_API_KEY=sk-xxx

# 搜索
SEARCH_ENABLED=true
SEARCH_BACKEND=duckduckgo
SEARCH_MAX_RESULTS=5
```

### 字段说明

| 字段 | 必需 | 说明 |
|---|---|---|
| `MODEL_<ID>_NAME` | 是 | 发送给 API 的实际模型名 |
| `MODEL_<ID>_PROVIDER` | 是 | `openai_compat` 或 `anthropic` |
| `MODEL_<ID>_API_BASE` | 否 | API endpoint，anthropic 等有默认地址的 provider 可省略 |
| `MODEL_<ID>_API_KEY` | 是 | API key 值，直接写入 |
| `MODEL_<ID>_VISION` | 否 | 是否支持图片，默认 false |

模型发现的规则：遍历所有 `MODEL_*_NAME` 环境变量，从变量名提取 `<ID>` 部分作为模型标识符。

Vision fallback 各字段独立，`VISION_FALLBACK_PROVIDER`、`VISION_FALLBACK_API_KEY`、`VISION_FALLBACK_NAME` 为必需，`VISION_FALLBACK_API_BASE` 可选。

## 命令行为

### `/model <ID>`
- 将当前会话的模型绑定切换为 `<ID>`，写入 SQLite
- 例如：`/model A` → 持久绑定到 A
- 不带参数则显示用法提示
- `<ID>` 必须是已配置的模型字母

### `/<ID> <消息>`
- 仅当前消息用 `<ID>` 模型处理，不写库
- 例如：`/B 今天天气怎么样` → 用 B 模型回复此条
- 下一条消息恢复之前的绑定模型或默认模型

### `/models`
- 列出所有可用模型：字母标识符、实际模型名、provider、vision 支持

## 配置加载

`lib/config.py` 的 `load_config()` 改为解析环境变量，不再读 YAML：

1. 通过 `MODEL_*_NAME` 模式发现所有模型
2. 每个模型读相关字段组装 `ModelConfig`
3. 读 `DEFAULT_MODEL`、vision fallback、search 配置
4. 启动时校验：
   - `DEFAULT_MODEL` 必须指向已配置的模型
   - 每个模型必须有 `NAME`、`PROVIDER`、`API_KEY`
   - 校验失败抛明确错误，不静默启动

## 数据结构变更

`ModelConfig` dataclass 增加 `api_key` 字段（值为直接可用的 key 字符串），保留 `api_key_env` 作为可选字段。

`AppConfig` 移除 `aliases` 字段。

`factory.py` 优先使用 `model_config.api_key`，未设则 fallback 到 `os.getenv(model_config.api_key_env)`。

## 用户交互示例

```
用户: /models
Bot:  可用模型：
      A - deepseek-chat (openai_compat) [默认]
      B - gpt-4o (openai_compat) [vision]
      C - claude-3.5-sonnet (anthropic) [vision]

用户: /model B
Bot:  模型已切换为 B (gpt-4o)

用户: /C 解释一下量子纠缠
Bot:  [用 claude 回复此条，绑定不变]

用户: 你好
Bot:  [用 B (gpt-4o) 回复，因为之前 /model B 已持久绑定]
```

## 涉及文件

| 文件 | 变更 |
|---|---|
| `.env.example` | 重写为新格式 |
| `config/models.yaml` | 删除 |
| `lib/config.py` | YAML 解析 → 环境变量解析，增加校验逻辑 |
| `lib/models/factory.py` | 支持 `api_key` 直接使用 |
| `src/plugins/chat/router.py` | 别名解析改为直接匹配模型字母前缀 |
| `src/plugins/chat/handlers.py` | `/models` 命令适配新数据结构 |

## 不变更

- `lib/db.py` 和 `lib/model_binding.py`：DB 表结构和绑定逻辑不变，只是 `model_name` 值从 `deepseek-v3` 变成 `A`
- `lib/ai_core.py`：模型调用流程不变
- `lib/models/openai_compat.py` / `anthropic.py`：provider 实现不变
- 测试文件：更新 mock 配置适配新格式
