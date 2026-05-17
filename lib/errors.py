from dataclasses import dataclass


# ── Error code registry ──────────────────────────────────────────────

@dataclass(frozen=True)
class ErrorDef:
    code: str
    name: str
    user_msg: str
    cause: str          # 可能原因
    suggestion: str     # 建议操作


ERROR_DEFS: dict[str, "ErrorDef"] = {}  # populated below


def _reg(code: str, name: str, user_msg: str, cause: str, suggestion: str) -> ErrorDef:
    d = ErrorDef(code, name, user_msg, cause, suggestion)
    ERROR_DEFS[code] = d
    return d


E01 = _reg("E01", "API_TIMEOUT",
    "服务响应超时，请稍后重试",
    "AI 服务商响应缓慢或当前网络不稳定",
    "等待几秒后重新发送消息；若持续出现可切换模型试试")

E02 = _reg("E02", "API_AUTH",
    "服务配置异常，请联系管理员",
    "API 密钥无效、过期或未正确配置",
    "检查 .env 中对应模型的 API_KEY 是否正确")

E03 = _reg("E03", "API_RATE",
    "服务繁忙或额度用尽，请稍后重试",
    "API 频率限制触发或账户额度耗尽",
    "等待片刻后重试；若频繁出现可切换模型或检查账户余额")

E04 = _reg("E04", "API_SERVER",
    "服务暂时不可用，请稍后重试",
    "AI 服务商服务器出现临时故障",
    "等待几分钟后重试，通常很快恢复")

E05 = _reg("E05", "API_NETWORK",
    "网络连接失败，请稍后重试",
    "DNS 解析失败或无法连接到 API 服务器",
    "检查服务器网络连通性，确认是否能访问外网")

E06 = _reg("E06", "SEARCH_FAIL",
    "搜索功能暂时不可用",
    "DuckDuckGo 搜索服务不可达或返回异常",
    "稍后重试；该错误不影响对话功能，可关闭搜索再试")

E07 = _reg("E07", "IMAGE_DOWNLOAD",
    "图片获取失败，请重新发送",
    "QQ 图片链接过期或下载超时",
    "重新发送图片；若持续失败可能是图片服务异常")

E08 = _reg("E08", "UNKNOWN",
    "发生未知错误，请稍后重试",
    "未预期的异常，可能是代码 bug 或环境问题",
    "稍后重试；若持续出现请联系管理员并提供错误码 E08")


# ── Exception hierarchy ──────────────────────────────────────────────

class BotException(Exception):
    """Base exception with error code."""
    def __init__(self, error_def: ErrorDef, detail: str = ""):
        self.error_def = error_def
        self.detail = detail
        super().__init__(f"[{error_def.code}] {error_def.name}: {detail}" if detail else f"[{error_def.code}] {error_def.name}")


# ── Error reply formatting ───────────────────────────────────────────

def format_error_reply(exc: BotException) -> str:
    """Format a BotException into the user-visible error reply string."""
    d = exc.error_def
    lines = [
        f"[{d.code}] {d.user_msg}",
        f"📋 可能原因：{d.cause}",
        f"💡 建议操作：{d.suggestion}",
    ]
    return "\n".join(lines)
