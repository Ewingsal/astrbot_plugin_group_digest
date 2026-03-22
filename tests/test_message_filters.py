from __future__ import annotations

from astrbot_plugin_group_digest.services.message_filters import (
    classify_plugin_owned_message,
    filter_effective_messages,
    is_plugin_command_message,
    is_plugin_output_message,
)
from astrbot_plugin_group_digest.services.models import MessageRecord


def _msg(content: str, *, sender_id: str = "u1", ts: int = 1) -> MessageRecord:
    return MessageRecord(
        group_id="group_1001",
        sender_id=sender_id,
        sender_name="Alice",
        content=content,
        timestamp=ts,
    )


def test_plugin_commands_are_classified() -> None:
    assert is_plugin_command_message("/group_digest")
    assert is_plugin_command_message("/group_digest_today")
    assert is_plugin_command_message("/group_digest_debug_today")


def test_digest_output_prefix_is_classified() -> None:
    assert is_plugin_output_message("群聊兴趣日报（2026-03-22）\n统计日期：2026-03-22")


def test_sender_based_bot_message_is_classified() -> None:
    reason = classify_plugin_owned_message(
        text="大家要不要把今天的重点结论整理成三条？",
        sender_id="bot_123",
        bot_sender_ids={"bot_123"},
    )
    assert reason == "plugin_sender_id"


def test_filter_effective_messages_excludes_plugin_owned_messages() -> None:
    rows = [
        _msg("普通聊天内容", sender_id="u1", ts=1),
        _msg("/group_digest_today", sender_id="u1", ts=2),
        _msg("群聊兴趣日报（2026-03-22）\n统计日期：2026-03-22", sender_id="u2", ts=3),
        _msg("bot 主动发言", sender_id="bot_123", ts=4),
    ]

    effective, reasons = filter_effective_messages(rows, bot_sender_ids={"bot_123"})

    assert len(effective) == 1
    assert effective[0].content == "普通聊天内容"
    assert reasons["plugin_command"] == 1
    assert reasons["plugin_output_prefix"] == 1
    assert reasons["plugin_sender_id"] == 1
