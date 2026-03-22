from __future__ import annotations

from .models import MessageRecord

PLUGIN_COMMANDS = (
    "/group_digest",
    "/group_digest_today",
    "/group_digest_debug_today",
)

PLUGIN_OUTPUT_PREFIXES = (
    "群聊兴趣日报（",
    "[调试] 今日消息统计",
)


def is_plugin_command_message(text: str) -> bool:
    if not text:
        return False

    normalized = text.strip()
    if not normalized:
        return False

    normalized = _strip_leading_mentions(normalized)
    if not normalized:
        return False

    for command in PLUGIN_COMMANDS:
        if normalized == command:
            return True
        if normalized.startswith(command):
            suffix = normalized[len(command) : len(command) + 1]
            if suffix in {"", " ", "\n", "\t", "\r", "@"}:
                return True
    return False


def is_plugin_output_message(text: str) -> bool:
    normalized = _normalize_for_match(text)
    if not normalized:
        return False
    return any(normalized.startswith(prefix) for prefix in PLUGIN_OUTPUT_PREFIXES)


def classify_plugin_owned_message(
    *,
    text: str,
    sender_id: str = "",
    bot_sender_ids: set[str] | None = None,
) -> str:
    if is_plugin_command_message(text):
        return "plugin_command"

    if is_plugin_output_message(text):
        return "plugin_output_prefix"

    if sender_id and bot_sender_ids and sender_id in bot_sender_ids:
        return "plugin_sender_id"

    return ""


def filter_effective_messages(
    messages: list[MessageRecord],
    *,
    bot_sender_ids: set[str] | None = None,
) -> tuple[list[MessageRecord], dict[str, int]]:
    effective: list[MessageRecord] = []
    reasons = {
        "plugin_command": 0,
        "plugin_output_prefix": 0,
        "plugin_sender_id": 0,
    }
    for row in messages:
        reason = classify_plugin_owned_message(
            text=row.content,
            sender_id=row.sender_id,
            bot_sender_ids=bot_sender_ids,
        )
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        effective.append(row)
    return effective, reasons


def effective_message_stats(messages: list[MessageRecord]) -> tuple[int, int]:
    count = len(messages)
    last_ts = max((row.timestamp for row in messages), default=0)
    return count, last_ts


def _strip_leading_mentions(text: str) -> str:
    current = text.lstrip()

    while current:
        if current.startswith("[CQ:at") and "]" in current:
            current = current.split("]", 1)[1].lstrip()
            continue

        if current.startswith("@"):
            parts = current.split(maxsplit=1)
            if len(parts) == 1:
                return ""
            current = parts[1].lstrip()
            continue

        break

    return current


def _normalize_for_match(text: str) -> str:
    if not text:
        return ""
    normalized = _strip_leading_mentions(text.strip())
    return normalized.strip()
