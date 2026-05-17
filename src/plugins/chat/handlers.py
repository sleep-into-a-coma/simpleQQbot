from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg

from lib.context import clear_history
from lib.permission import check_permission, set_permission, get_rate_limit_status, get_private_chat_enabled, set_private_chat_enabled
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
/ban @某人 - 禁止某人使用 Bot（管理员）
/hire <群号> - 授权群使用 Bot（管理员）
/fire <群号> - 撤销群使用权限（管理员）
/allow-p @某人 - 授权某人私聊 Bot（管理员）
/ban-p @某人 - 撤销某人私聊权限（管理员）
/private on/off - 全局私聊开关（管理员）
/admin - 查看管理面板（管理员）"""
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


hire_cmd = on_command("hire", priority=10)

@hire_cmd.handle()
async def handle_hire(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await hire_cmd.finish("权限不足。")
    target = args.extract_plain_text().strip()
    if not target:
        await hire_cmd.finish("用法：/hire <群号>")
    target_id = target
    await set_permission("group", target_id, "allow")
    await hire_cmd.finish(f"已授权群 {target_id} 使用 Bot。")


fire_cmd = on_command("fire", priority=10)

@fire_cmd.handle()
async def handle_fire(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await fire_cmd.finish("权限不足。")
    target = args.extract_plain_text().strip()
    if not target:
        await fire_cmd.finish("用法：/fire <群号>")
    target_id = target
    await set_permission("group", target_id, "block")
    await fire_cmd.finish(f"已禁止群 {target_id} 使用 Bot。")


allow_p_cmd = on_command("allow-p", priority=10)

@allow_p_cmd.handle()
async def handle_allow_p(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await allow_p_cmd.finish("权限不足。")
    target = args.extract_plain_text().strip()
    if not target:
        await allow_p_cmd.finish("用法：/allow-p @某人 或 /allow-p QQ号")
    target_id = _extract_qq(target)
    await set_permission("private_chat", target_id, "allow")
    await allow_p_cmd.finish(f"已授权 {target_id} 私聊使用 Bot。")


ban_p_cmd = on_command("ban-p", priority=10)

@ban_p_cmd.handle()
async def handle_ban_p(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await ban_p_cmd.finish("权限不足。")
    target = args.extract_plain_text().strip()
    if not target:
        await ban_p_cmd.finish("用法：/ban-p @某人 或 /ban-p QQ号")
    target_id = _extract_qq(target)
    await set_permission("private_chat", target_id, "block")
    await ban_p_cmd.finish(f"已禁止 {target_id} 私聊使用 Bot。")


private_cmd = on_command("private", priority=10)

@private_cmd.handle()
async def handle_private(event: MessageEvent, args: Message = CommandArg()):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await private_cmd.finish("权限不足。")
    action = args.extract_plain_text().strip()
    if action not in ("on", "off"):
        await private_cmd.finish("用法：/private on 或 /private off")
    enabled = action == "on"
    await set_private_chat_enabled(enabled)
    await private_cmd.finish(f"私聊功能已{'开启' if enabled else '关闭'}。")


admin_cmd = on_command("admin", priority=10)

@admin_cmd.handle()
async def handle_admin(event: MessageEvent):
    user_id = str(event.user_id)
    if user_id not in app_config.admins:
        await admin_cmd.finish("权限不足。")

    from lib.db import get_db

    lines = ["=== Bot 管理面板 ===", ""]

    # Static config
    lines.append("【静态白名单 (yaml)】")
    lines.append(f"  管理员: {', '.join(app_config.admins) if app_config.admins else '未配置'}")
    lines.append(f"  白名单用户: {', '.join(app_config.whitelist_users) if app_config.whitelist_users else '未限制'}")
    lines.append(f"  白名单群: {', '.join(app_config.whitelist_groups) if app_config.whitelist_groups else '未限制'}")
    lines.append("")

    # Dynamic permissions
    db = await get_db()
    try:
        cursor = await db.execute("SELECT target_type, target_id, level FROM permissions ORDER BY target_type, target_id")
        rows = await cursor.fetchall()
        lines.append("【动态权限 (DB)】")
        if rows:
            for row in rows:
                type_label = {"user": "用户", "group": "群", "private_chat": "私聊"}.get(row["target_type"], row["target_type"])
                level_label = "允许" if row["level"] == "allow" else "禁止"
                lines.append(f"  [{type_label}] {row['target_id']} → {level_label}")
        else:
            lines.append("  无")
    finally:
        await db.close()

    lines.append("")

    # Private chat toggle
    pc_enabled = await get_private_chat_enabled()
    lines.append(f"【私聊开关】: {'开启' if pc_enabled else '关闭'}")
    lines.append("")

    # Rate limits
    lines.append("【频率限制】")
    lines.append(f"  用户: {app_config.rate_limit_user_per_minute}/分钟")
    lines.append(f"  群: {app_config.rate_limit_group_per_minute}/分钟")

    await admin_cmd.finish("\n".join(lines))


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
