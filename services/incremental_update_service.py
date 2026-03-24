from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from astrbot.api import logger

from .models import MemberDigest, MessageRecord


@dataclass(frozen=True)
class EffectiveMessageState:
    message_count: int
    last_message_ts: int
    last_message_fingerprint: str


class IncrementalUpdateService:
    """轻量增量更新工具：消息边界识别 + 规则统计增量合并。"""

    def sort_messages(self, messages: list[MessageRecord]) -> list[MessageRecord]:
        return sorted(
            messages,
            key=lambda item: (
                item.timestamp,
                item.message_id or "",
                item.sender_id,
                self._content_hash(item.content),
            ),
        )

    def build_message_fingerprint(self, row: MessageRecord) -> str:
        message_id = str(getattr(row, "message_id", "") or "").strip()
        if message_id:
            return f"id:{message_id}"
        return f"fallback:{row.timestamp}:{row.sender_id}:{self._content_hash(row.content)}"

    def build_effective_state(self, messages: list[MessageRecord]) -> EffectiveMessageState:
        ordered = self.sort_messages(messages)
        if not ordered:
            return EffectiveMessageState(
                message_count=0,
                last_message_ts=0,
                last_message_fingerprint="",
            )

        last = ordered[-1]
        return EffectiveMessageState(
            message_count=len(ordered),
            last_message_ts=last.timestamp,
            last_message_fingerprint=self.build_message_fingerprint(last),
        )

    def locate_delta_messages(
        self,
        *,
        messages: list[MessageRecord],
        checkpoint_last_message_ts: int,
        checkpoint_last_message_fingerprint: str,
    ) -> tuple[str, list[MessageRecord]]:
        if checkpoint_last_message_ts <= 0 or not checkpoint_last_message_fingerprint:
            return "checkpoint_boundary_missing", []

        ordered = self.sort_messages(messages)
        if not ordered:
            return "no_messages_in_window", []

        boundary_idx = -1
        for idx in range(len(ordered) - 1, -1, -1):
            row = ordered[idx]
            if row.timestamp != checkpoint_last_message_ts:
                continue
            if self.build_message_fingerprint(row) == checkpoint_last_message_fingerprint:
                boundary_idx = idx
                break

        if boundary_idx < 0:
            return "checkpoint_boundary_not_found", []

        return "", ordered[boundary_idx + 1 :]

    def build_stats_state_from_messages(self, messages: list[MessageRecord]) -> dict[str, Any]:
        member_counts: dict[str, dict[str, Any]] = {}
        for row in messages:
            key = row.sender_id
            entry = member_counts.get(key)
            if entry is None:
                member_counts[key] = {
                    "sender_name": row.sender_name,
                    "message_count": 1,
                }
                continue
            entry["message_count"] = self._safe_int(entry.get("message_count", 0)) + 1
            if not str(entry.get("sender_name", "")).strip() and row.sender_name:
                entry["sender_name"] = row.sender_name

        total_messages = sum(
            self._safe_int(item.get("message_count", 0))
            for item in member_counts.values()
        )
        return {
            "total_messages": total_messages,
            "participant_count": len(member_counts),
            "member_message_counts": member_counts,
        }

    def normalize_stats_state(self, state: Any) -> dict[str, Any] | None:
        if not isinstance(state, dict):
            return None
        if "member_message_counts" not in state:
            return None

        raw_members = state.get("member_message_counts", {})
        if not isinstance(raw_members, dict):
            return None

        members: dict[str, dict[str, Any]] = {}
        for sender_id, raw in raw_members.items():
            if not isinstance(raw, dict):
                continue
            sid = str(sender_id).strip()
            if not sid:
                continue
            count = self._safe_int(raw.get("message_count", 0))
            if count < 0:
                count = 0
            members[sid] = {
                "sender_name": str(raw.get("sender_name", sid)).strip() or sid,
                "message_count": count,
            }

        total_messages = self._safe_int(state.get("total_messages", 0))
        if total_messages < 0:
            total_messages = 0
        participant_count = self._safe_int(state.get("participant_count", len(members)))
        if participant_count < 0:
            participant_count = 0

        # 以成员累计值为准，避免 total_messages 与明细不一致导致状态漂移。
        summarized_total = sum(
            self._safe_int(item.get("message_count", 0))
            for item in members.values()
        )

        return {
            "total_messages": summarized_total if summarized_total >= 0 else total_messages,
            "participant_count": len(members) if members else participant_count,
            "member_message_counts": members,
        }

    def apply_delta_to_stats_state(
        self,
        *,
        base_state: Any,
        delta_messages: list[MessageRecord],
    ) -> dict[str, Any] | None:
        state = self.normalize_stats_state(base_state)
        if state is None:
            return None

        merged_members = {
            sender_id: {
                "sender_name": str(item.get("sender_name", sender_id)),
                "message_count": self._safe_int(item.get("message_count", 0)),
            }
            for sender_id, item in state["member_message_counts"].items()
            if isinstance(item, dict)
        }

        for row in delta_messages:
            entry = merged_members.get(row.sender_id)
            if entry is None:
                merged_members[row.sender_id] = {
                    "sender_name": row.sender_name,
                    "message_count": 1,
                }
                continue

            entry["message_count"] = self._safe_int(entry.get("message_count", 0)) + 1
            if row.sender_name:
                entry["sender_name"] = row.sender_name

        total_messages = sum(
            self._safe_int(item.get("message_count", 0))
            for item in merged_members.values()
        )
        return {
            "total_messages": total_messages,
            "participant_count": len(merged_members),
            "member_message_counts": merged_members,
        }

    def build_active_members_from_stats_state(
        self,
        *,
        state: Any,
        max_active_members: int,
    ) -> list[MemberDigest]:
        normalized = self.normalize_stats_state(state)
        if normalized is None:
            return []

        rows: list[MemberDigest] = []
        for sender_id, item in normalized["member_message_counts"].items():
            if not isinstance(item, dict):
                continue
            rows.append(
                MemberDigest(
                    sender_id=sender_id,
                    sender_name=str(item.get("sender_name", sender_id)).strip() or sender_id,
                    message_count=max(0, self._safe_int(item.get("message_count", 0))),
                )
            )

        rows.sort(key=lambda item: (-item.message_count, item.sender_name))
        return rows[:max_active_members]

    def _content_hash(self, content: str) -> str:
        text = str(content or "")
        return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]

    def _safe_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            logger.warning(
                "[group_digest.incremental] invalid_int value=%r fallback=%d",
                value,
                default,
            )
            return default
