# 群聊历史修复 + 用户名称注册设计

## 概述

两个关联改动：

1. **群聊历史修复** — `get_history` 群聊场景不再按 `user_id` 过滤，返回群内所有消息并标注发言者名称
2. **用户名称注册** — `/register` 指令绑定 QQ 号 → 可读名称，群聊消息用名称标记发言人

## 数据模型

### user_names 表（新建）

```sql
CREATE TABLE IF NOT EXISTS user_names (
    user_id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
```

写入逻辑：`INSERT OR REPLACE`，后注册自动覆盖旧名。

### 群聊历史查询修复

`get_history(group_id, user_id)` 行为变更：

| 场景 | 原行为 | 新行为 |
|------|--------|--------|
| `group_id != "private"` | `WHERE group_id=? AND user_id=?` | `WHERE group_id=?` 返回群内全部消息，附带 user_id |
| `group_id == "private"` | `WHERE group_id=? AND user_id=?` | 不变，仍按 user_id 过滤 |

返回值从 `list[dict]` 改为包含 user_id：
```python
[{"role": "user", "content": "...", "user_id": "123456"}, ...]
```

## 消息格式

### 群聊

**历史消息：**
```
<群聊消息>小明说：今天天气真好
</群聊消息>
```

发言人通过 `user_names` 表查找 user_id → name；未注册用户 fallback 为 `用户123456`。

AI 回复与历史对齐，用相同的 `<群聊消息>` 标签。

**当前用户消息保持现有格式：**
```
<用户消息>内容</用户消息>
```
这样可以区分"当前请求者"和"历史中的其他人"。

### 私聊

不变：`<用户消息>内容</用户消息>`

### /summarize 中的历史

也需要适配——使用群聊消息格式或私聊格式。

## 指令

| 指令 | 权限 | 功能 |
|------|------|------|
| `/register <名字>` | 所有人 | 给自己的 QQ 号绑定一个名称 |
| `/register @某人 <名字>` | admin | 给指定用户绑定名称 |

示例：
- `/register 小明` → 当前用户绑定为 "小明"
- `/register @123456 小明` → admin 给 123456 绑定为 "小明"

## 约束

- 群聊中 user_id 维度保留存储，仅不再作为查询过滤条件
- 私聊查询行为不变
- `/register` 不区分给自己还是给别人的权限——用户可自由给自己起名，admin 可给任何人起名
- 改名就是覆盖，没有"找回旧名"机制

## 需要改动的文件

| 文件 | 改动 |
|------|------|
| `lib/db.py` | `init_db` 新增 `user_names` 表 |
| `lib/context.py` | `get_history` 群聊按 group_id 查全群；返回值增加 user_id |
| `lib/ai_core.py` | `_build_initial_messages` 群聊历史包装为 `<群聊消息>`，解析发言人名称 |
| `lib/permission.py` | 新增 `set_user_name` / `get_user_name` / `get_group_user_names` |
| `src/plugins/chat/handlers.py` | 新增 `/register` 指令，更新 `/help` |
| `README.md` | 更新指令列表 |
