# hire/fire 群权限 + 私聊控制 + /admin 设计

## 概述

新增群维度动态权限 (`/hire` `/fire`)、私聊用户授权 (`/allow-p` `/ban-p`)、全局私聊开关 (`/private on/off`)、以及管理员元数据展示指令 (`/admin`)。

## 数据层

### permissions 表（已有，不改结构）

复用现有 `permissions` 表，通过 `target_type` 区分权限类型：

| target_type | 指令 |
|-------------|------|
| `user` | `/allow` `/ban` |
| `group` | `/hire` `/fire` |
| `private_chat` | `/allow-p` `/ban-p` |

### settings 表（新建）

```sql
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

初始值在 `init_db` 时从 `permissions.yaml` 写入。

### permissions.yaml 新增

```yaml
private_chat:
  enabled: true
```

## 指令

### /hire /fire — 群权限（admin only）

- `/hire <群号>` → `set_permission("group", target_id, "allow")`
- `/fire <群号>` → `set_permission("group", target_id, "block")`

### /allow-p /ban-p — 私聊用户权限（admin only）

- `/allow-p <QQ号>` → `set_permission("private_chat", target_id, "allow")`
- `/ban-p <QQ号>` → `set_permission("private_chat", target_id, "block")`

### /private on/off — 全局私聊开关（admin only）

- 写入 `settings` 表 `private_chat_enabled` = `"1"` / `"0"`
- 同时返回内存 `app_config`（或每次从 DB 读取，简单方案：每次读 DB）

### /admin — 管理员元数据展示（admin only）

一次展示：
- 静态白名单（admins, whitelist_users, whitelist_groups — yaml）
- 动态权限列表（全部 permissions 表数据）
- 私聊开关状态
- 频率限制配置

## 私聊消息检查

新增函数 `check_private_chat_permission(user_id)` 或扩展现有 `check_permission`：

```
私聊消息进入
  → private_chat_enabled = false？ → 拒绝："私聊功能已关闭"
  → 用户有 private_chat block 动态规则？ → 拒绝
  → 用户有 private_chat allow 动态规则？ → 放行
  → 无动态规则 → 走现有 check_permission（静态白名单逻辑）
```

## 需要改动的文件

| 文件 | 改动 |
|------|------|
| `lib/db.py` | `init_db` 新增 `settings` 表，写入默认值 |
| `lib/permission.py` | 新增 `check_private_chat_permission`、`get_private_chat_enabled`、`set_private_chat_enabled` |
| `lib/config.py` | `_load_permissions` 新增 `private_chat_enabled` 字段；`AppConfig` 新增该字段 |
| `config/permissions.yaml` | 新增 `private_chat.enabled` |
| `src/plugins/chat/handlers.py` | 新增 `/hire` `/fire` `/allow-p` `/ban-p` `/private` `/admin` 指令；更新 `/help` |
| `src/plugins/chat/router.py` | 私聊消息进入时增加 `check_private_chat_permission` |
| `README.md` | 更新指令列表 |

## 约束

- 所有新增指令均为 admin only
- `/hire` `/fire` 和 `/allow` `/ban` 共享 `set_permission` 函数，仅 target_type 不同
- 不要创建单独的表给群权限或私聊权限，统一复用 permissions
- 不要修改现有 `/allow` `/ban` 行为
