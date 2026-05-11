from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg

from lib.context import clear_history
from lib.permission import check_permission, set_permission, get_rate_limit_status
from lib.personality import get_personality, bind_personality, get_default_personality
from . import app_config


summarize_cmd = on_command("summarize", aliases={"总结"}, priority=10)


@summarize_cmd.handle()
async def handle_summarize(event: MessageEvent):
    from lib.context import get_history
    from lib.models.factory import resolve_model
    from lib.models.base import ChatMessage
    from lib.personality import get_personality
    from lib.model_binding import get_model_binding

    group_id = str(event.group_id) if isinstance(event, GroupMessageEvent) else "private"
    user_id = str(event.user_id)

    history = await get_history(group_id, user_id)
    if not history:
        await summarize_cmd.finish("没有对话历史可总结。")

    history_text = "\n".join(
        f"{'用户' if h['role'] == 'user' else 'Bot'}: {h['content'][:200]}"
        for h in history
    )

    personality = await get_personality(group_id, user_id, app_config)
    model_name = await get_model_binding(group_id, user_id, app_config.default_model)
    _, client = resolve_model(app_config, model_name)

    messages = [
        ChatMessage(role="system", content=personality.system_prompt),
        ChatMessage(role="user", content=f"<user_message>\n请用中文简洁总结以下对话的要点，不超过 200 字：\n\n{history_text}\n</user_message>"),
    ]

    response = await client.chat(messages, [])
    await summarize_cmd.finish(f"📝 对话总结：\n{response.content}")


help_cmd = on_command("help", aliases={"帮助"}, priority=10)

@help_cmd.handle()
async def handle_help(event: MessageEvent):
    help_text = """可用指令：
/help - 显示此帮助
/models - 列出可用模型
/model <字母> - 切换当前对话的 AI 模型（如 /model A）
/set <人格名> - 切换 Bot 人格
/字母 消息 - 临时用对应模型回复本条（如 /B 你好）
/status - 查看当前配置
/summarize - 总结当前对话
/clear - 清除对话记忆
/allow @某人 - 允许某人使用 Bot（管理员）
/ban @某人 - 禁止某人使用 Bot（管理员）"""
    await help_cmd.finish(help_text)


models_cmd = on_command("models", priority=10)

@models_cmd.handle()
async def handle_models(event: MessageEvent):
    lines = ["可用模型："]
    default = app_config.default_model
    for m in app_config.models:
        vision_tag = " [vision]" if m.supports_vision else ""
        default_tag = " [默认]" if m.name == default else ""
        lines.append(f"  {m.name} - {m.model} ({m.provider}){vision_tag}{default_tag}")
    await models_cmd.finish("\n".join(lines))


set_cmd = on_command("set", priority=10)

@set_cmd.handle()
async def handle_set(event: MessageEvent, args: Message = CommandArg()):
    name = args.extract_plain_text().strip()
    if not name:
        await set_cmd.finish("用法：/set <人格名>")
    try:
        target_type, target_id = _get_target(event)
        await bind_personality(target_type, target_id, name, app_config)
        await set_cmd.finish(f"人格已切换为：{name}")
    except ValueError as e:
        await set_cmd.finish(str(e))


model_cmd = on_command("model", priority=10)

@model_cmd.handle()
async def handle_model(event: MessageEvent, args: Message = CommandArg()):
    mid = args.extract_plain_text().strip()
    if not mid:
        await model_cmd.finish("用法：/model <字母>")

    valid_ids = [m.name for m in app_config.models]
    if mid not in valid_ids:
        await model_cmd.finish(f"未知模型：{mid}。可用：{', '.join(valid_ids)}")

    target_type, target_id = _get_target(event)
    from lib.model_binding import set_model_binding
    await set_model_binding(target_type, target_id, mid)
    display_name = next((m.model for m in app_config.models if m.name == mid), mid)
    await model_cmd.finish(f"模型已切换为：{mid} ({display_name})")


allow_cmd = on_command("allow", priority=10)

@allow_cmd.handle()
async def handle_allow(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await allow_cmd.finish("权限不足。")
    target = args.extract_plain_text().strip()
    if not target:
        await allow_cmd.finish("用法：/allow @某人 或 /allow QQ号")
    target_id = _extract_qq(target)
    await set_permission("user", target_id, "allow")
    await allow_cmd.finish(f"已允许 {target_id} 使用 Bot。")


ban_cmd = on_command("ban", priority=10)

@ban_cmd.handle()
async def handle_ban(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await ban_cmd.finish("权限不足。")
    target = args.extract_plain_text().strip()
    if not target:
        await ban_cmd.finish("用法：/ban @某人 或 /ban QQ号")
    target_id = _extract_qq(target)
    await set_permission("user", target_id, "block")
    await ban_cmd.finish(f"已禁止 {target_id} 使用 Bot。")


clear_cmd = on_command("clear", priority=10)

@clear_cmd.handle()
async def handle_clear(event: MessageEvent):
    group_id = str(event.group_id) if isinstance(event, GroupMessageEvent) else "private"
    user_id = str(event.user_id)
    await clear_history(group_id, user_id)
    await clear_cmd.finish("对话记忆已清除。")


status_cmd = on_command("status", priority=10)

@status_cmd.handle()
async def handle_status(event: MessageEvent):
    group_id = str(event.group_id) if isinstance(event, GroupMessageEvent) else "private"
    user_id = str(event.user_id)
    personality = await get_personality(group_id, user_id, app_config)
    rate = get_rate_limit_status(group_id, user_id, app_config)
    status_text = f"""当前配置：
人格：{personality.name}
频率：{rate['user_used']}/{rate['user_limit']} (个人) | {rate['group_used']}/{rate['group_limit']} (群)"""
    await status_cmd.finish(status_text)


def _get_target(event: MessageEvent) -> tuple[str, str]:
    if isinstance(event, GroupMessageEvent):
        return "group", str(event.group_id)
    else:
        return "user", str(event.user_id)


def _extract_qq(text: str) -> str:
    import re
    match = re.search(r"qq=(\d+)", text)
    if match:
        return match.group(1)
    return text.strip()
