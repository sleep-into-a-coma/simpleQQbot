import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import SYSTEM_RULE


def test_system_rule_appended_to_prompt():
    """system_rule must be appended to every system prompt."""
    from lib.config import _load_personalities
    _, personalities = _load_personalities()
    for p in personalities:
        assert p.system_prompt.endswith(SYSTEM_RULE), f"Personality '{p.name}': SYSTEM_RULE must be at the END"


def test_system_rule_content():
    """Verify the system_rule contains key defense instructions."""
    assert "<system_rule>" in SYSTEM_RULE
    assert "</system_rule>" in SYSTEM_RULE
    assert "忽略规则" in SYSTEM_RULE
    assert "扮演其他角色" in SYSTEM_RULE
    assert "输出系统提示词" in SYSTEM_RULE


from lib.ai_core import _build_initial_messages
from lib.models.base import ChatMessage


def test_user_messages_wrapped_in_xml():
    """All user-role messages must be wrapped in <user_message> tags."""
    messages = _build_initial_messages(
        system_prompt="You are helpful.",
        history=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ],
        user_text="how are you",
        image_data=None,
    )

    user_msgs = [m for m in messages if m.role == "user"]
    assert len(user_msgs) == 2  # history + current

    assert "<user_message>" in user_msgs[0].content
    assert "hello" in user_msgs[0].content
    assert "</user_message>" in user_msgs[0].content

    assert "<user_message>" in user_msgs[1].content
    assert "how are you" in user_msgs[1].content
    assert "</user_message>" in user_msgs[1].content


def test_assistant_messages_not_wrapped():
    """Assistant messages must NOT be wrapped."""
    messages = _build_initial_messages(
        system_prompt="You are helpful.",
        history=[
            {"role": "assistant", "content": "I am a bot"},
        ],
        user_text="hello",
        image_data=None,
    )
    assistant_msgs = [m for m in messages if m.role == "assistant"]
    assert len(assistant_msgs) == 1
    assert "<user_message>" not in assistant_msgs[0].content


import re


def test_cq_pattern_strips_basic():
    pattern = re.compile(r'\[CQ:[^\]]+\]')
    result = pattern.sub('', "hello [CQ:image,file=abc] world")
    assert result == "hello  world"


def test_cq_pattern_strips_multiple():
    pattern = re.compile(r'\[CQ:[^\]]+\]')
    result = pattern.sub('', "[CQ:at,qq=123]你好[CQ:image,url=x]再见")
    assert result == "你好再见"


def test_cq_pattern_no_cq_unchanged():
    pattern = re.compile(r'\[CQ:[^\]]+\]')
    result = pattern.sub('', "普通文本没有CQ码")
    assert result == "普通文本没有CQ码"


def test_cq_pattern_nested_brackets():
    """CQ codes with URLs in data should be handled."""
    pattern = re.compile(r'\[CQ:[^\]]+\]')
    result = pattern.sub('', "pre [CQ:image,file=http://x.com/a.jpg] post")
    assert result == "pre  post"
