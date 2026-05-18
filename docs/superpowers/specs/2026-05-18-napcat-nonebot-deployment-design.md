# NapCat + NoneBot 一键部署设计

## 目标

将 napcat 和 nonebot bot 打包为一键部署方案，同时支持 Docker Compose 和裸机脚本两种方式。bot 代码改动最小化。

## 架构

```
Docker Compose                            裸机部署

┌──────────┐  Reverse WS   ┌───────────┐  NapCat 二进制 ──WS──→ python bot.py
│  NapCat  │ ────────────→ │  QQBot    │   127.0.0.1:8989
│ (官方镜像)│   :8989/ws    │ (自建Docker)│
└──────────┘               └───────────┘
      │                          │
      └── internal network ──────┘
```

连接模式：反向 WebSocket（NapCat 作为 WS 客户端主动连接 NoneBot），沿用现有架构。

## Docker Compose 设计

### 服务编排

- **bot 服务**：自建 Dockerfile，端口 8989，internal network
- **napcat 服务**：官方镜像 `napcat/napcat`，依赖 bot 健康检查通过后启动
- **internal network**：bridge 驱动，容器间通过 hostname 通信

### 关键细节

- NapCat 的 `depends_on: service_healthy`，等 bot 的 8989 端口就绪
- bot Dockerfile 新增 `HEALTHCHECK`（socket 探测 8989 端口）
- `HEALTHCHECK --interval=5s --timeout=3s --retries=10 CMD python -c "import socket; s=socket.socket(); s.connect(('127.0.0.1', 8989)); s.close()"`

### 数据持久化

| 路径 | 内容 | 说明 |
|------|------|------|
| `./napcat/config` → `/app/config` | onebot11.json | WS 连接配置 |
| `./napcat/data` → `/app/data` | QQ 登录会话 | 删则需重新扫码 |
| `./napcat/cache` → `/app/cache` | 图片/文件缓存 | 可选，防止膨胀 |
| `./config` → `/app/config:ro` | bot 人格/权限 | 只读 |
| `./data` → `/app/data` | SQLite、日志 | 持久化 |
| `./.env` → `/app/.env:ro` | 模型密钥 | 只读 |

## 裸机安装脚本

`scripts/install.sh` 替代现有 `scripts/install-service.sh`，流程：

1. 检测 OS（Ubuntu/Debian/CentOS）
2. 安装系统依赖（python3, git, wget）
3. Python 虚拟环境 + pip install
4. 交互式生成 .env（可跳过）
5. 下载 NapCat 二进制到 `~/napcat/`
6. 写入 NapCat 反向 WS 配置
7. 安装两个 systemd 服务（qqbot + napcat）
8. 提示扫码登录

### systemd 服务

- **qqbot.service**：已有，不变。`Restart=on-failure`，崩溃自动重启
- **napcat.service**：新增。`After=qqbot.service`，等 bot 先启动

## NapCat 配置模板

`config/napcat.onebot11.json`：

```json
{
    "network": {
        "ws_reverse": [
            {
                "enable": true,
                "url": "ws://{HOST}:8989/onebot/v11/ws",
                "access_token": ""
            }
        ]
    }
}
```

`{HOST}` 根据部署环境替换：
- Docker → `bot`（容器服务名）
- 裸机 → `127.0.0.1`

## Bot 代码改动

### bot.py — 补 dotenv 加载

```python
from dotenv import load_dotenv
load_dotenv()

import nonebot
# ... 其余不变
```

与 `server/bot.py` 对齐，确保裸机部署时 `.env` 被正确加载。

### .env — 新增可选变量

```
ONEBOT_WS_PORT=8989
```

允许自定义 WS 端口，默认 8989。

### Dockerfile — 新增 HEALTHCHECK

```dockerfile
HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('127.0.0.1', 8989)); s.close()"
```

### 不改的部分

- `router.py`、`handlers.py`、`lib/` 全都不动
- OneBot V11 适配器和反向 WS 由 NoneBot 内部处理

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `bot.py` | 补 dotenv 加载 |
| 修改 | `Dockerfile` | 加 HEALTHCHECK |
| 修改 | `docker-compose.yml` | 加 napcat 服务 + network |
| 新增 | `config/napcat.onebot11.json` | NapCat 配置模板 |
| 新增 | `scripts/install.sh` | 裸机一键安装脚本 |
| 修改 | `.env.example` | 加 ONEBOT_WS_PORT 注释 |
| 删除 | `scripts/install-service.sh` | 被 install.sh 替代 |

## 扫码登录流程

1. `docker compose up` 或裸机 `systemctl start napcat`
2. `docker compose logs napcat` 或 `journalctl -u napcat -f` 看日志
3. 终端输出二维码链接，浏览器打开，QQ 小号扫码
4. 登录会话持久化到 volume/data 目录，重启无需重新扫码

## 实施时待验证

- NapCat 官方镜像名和内部配置路径以 napcat 官方文档为准（镜像可能从 Docker Hub 或 GitHub Container Registry 拉取，config 路径可能是 `/app/config/` 或 `/app/napcat/`）
- Health check 端口探测在 slim 镜像中 `python -c` 行为正常
- NapCat 二进制下载地址需确认最新 release 的 URL 格式

## 验收标准

1. `docker compose up` 后两个容器都 running，bot 能收发消息
2. 重启容器无需重新扫码
3. 裸机 `bash scripts/install.sh` 后 systemd 两个服务正常运行
4. bot 原有功能（/命令、AI 回复、图片识别等）均不受影响
