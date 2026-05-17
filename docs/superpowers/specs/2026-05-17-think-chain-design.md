# 思维链（think）功能设计

## 概述

支持 AI 思维链/推理过程的捕获与展示：全局开关 `/think on/off` + 单次触发 `<think>` 标签。思维链循环存入 think_history 表（每群 3 条 slot），用户通过 `/Thistory <N>` 回看。

## 数据模型

### ChatResponse 扩展

```python
@dataclass
class ChatResponse:
    content: str
    thinking: str = ""          # 新增：思维链内容
    tool_calls: list[ToolCall] = field(default_factory=list)
```

### think_history 表（新建）

```sql
CREATE TABLE IF NOT EXISTS think_history (
    group_id TEXT NOT NULL,
    slot INTEGER NOT NULL,       -- 1/2/3 循环槽位
    user_msg TEXT,
    thinking TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_id, slot)
);
```

### settings 表（复用）

新增 key `think_enabled`，`/think on/off` 写入，初始值从配置读。

### permissions.yaml 新增

```yaml
think_enabled: false
```

## Provider 捕获

| Provider | 来源 | 处理 |
|----------|------|------|
| OpenAI 兼容 | `reasoning_content` 字段（DeepSeek-R1 等） | 读 response choices[i].message.reasoning_content |
| Anthropic | `thinking` 类型 content block | 拼接所有 thinking block 的 text |

## 消息流程

```
用户消息: "今天天气怎么样<think>"
  → 检测末尾 <think>，剥离标签
  → msg_text = "今天天气怎么样"
  → think_triggered = think_enabled OR <think> detected
  → AI 调用时传递 thinking 参数（各 provider 按需配置）
  → 捕获 ChatResponse.thinking
  → 存入 think_history（循环 slot: counter%3+1）
  → 回复: content [+ thinking 如果触发]
  → 末尾追加提示: "（输入 /Thistory 1 查看本条思维链）"
```

## 指令

| 指令 | 权限 | 功能 |
|------|------|------|
| `/think on/off` | admin | 全局思维链开关，写入 settings 表 |
| `/Thistory <N>` | 所有人 | 查看当前群第 N 条思维链（N=1/2/3） |

## 提示规则

- 仅在思维链被记录时（think_enabled 或 `<think>` 触发）追加 `/Thistory` 提示
- 未触发时不记录、不提示、不存储

## 需要改动的文件

| 文件 | 改动 |
|------|------|
| `lib/models/base.py` | ChatResponse 新增 thinking 字段 |
| `lib/models/openai_compat.py` | 捕获 reasoning_content |
| `lib/models/anthropic.py` | 捕获 thinking blocks |
| `lib/ai_core.py` | process_message 传递 think 参数，解析 thinking |
| `lib/db.py` | init_db 新增 think_history 表，seed think_enabled |
| `lib/permission.py` | 新增 get_think_enabled / set_think_enabled / save_think_history / get_think_history |
| `config/permissions.yaml` | 新增 think_enabled |
| `lib/config.py` | AppConfig + _load_permissions 新增 think_enabled |
| `src/plugins/chat/router.py` | 检测 <think> 标签并剥离，think_triggered 传参，追加提示 |
| `src/plugins/chat/handlers.py` | 新增 /think 和 /Thistory 指令，更新 /help |
| `README.md` | 更新指令列表 |
