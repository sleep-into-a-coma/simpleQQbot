# PrismBot

基于 [NoneBot2](https://github.com/nonebot/nonebot2) 的 QQ 群聊 AI Bot，支持多模型切换、多人格、图片识别、联网搜索。

## 功能

- **多模型** — 同时挂载多个 AI 模型（OpenAI / Anthropic / DeepSeek 等），`/A` `/B` 即时切换
- **多人格** — 可配置多种 Bot 性格，按群或按用户绑定
- **图片识别** — 发图自动调 Vision 模型描述，非 Vision 模型自动降级
- **联网搜索** — 支持 DuckDuckGo / Bing / SearXNG，回复自带来源链接
- **对话记忆** — SQLite 上下文记忆，群聊全群共享、私聊按用户隔离
- **权限控制** — 白名单 + 动态授权 + 私聊开关
- **频率限制** — 用户/群双维度限流
- **思维链** — `/think on` 显示 AI 推理过程，`<think>` 单次触发

## 快速开始

### Windows

1. 下载 [最新发布](https://github.com/sleep-into-a-coma/PrismBot/releases)
2. 解压，复制 `.env.example` 为 `.env`，填写 API Key
3. 双击 `start.bat`

### Linux

```bash
tar -xzf PrismBot-linux-light.tar.gz && cd PrismBot && bash install.sh
```

### Docker

```bash
git clone https://github.com/sleep-into-a-coma/PrismBot.git
cd PrismBot && cp .env.example .env && nano .env
docker compose up -d
```

## 文档

完整文档见 **[Wiki](../../wiki)**：

- [配置参考](../../wiki/配置参考) — `.env` / `permissions.yaml` / `personalities.yaml` 详解
- [指令列表](../../wiki/指令列表) — 所有可用命令与权限说明
- [错误码](../../wiki/错误码) — API 异常排查
- [常见问题](../../wiki/常见问题) — FAQ
- [开发指南](../../wiki/开发指南) — 源码安装与项目结构

## 许可证

仅供个人使用、学习研究、非商业用途。
