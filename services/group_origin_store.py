from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class GroupOriginRecord:
    group_id: str
    unified_msg_origin: str
    last_active_at: int
    updated_at: str


class GroupOriginStore:
    """持久化群聊会话标识（group_id -> unified_msg_origin）。"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write_raw({"groups": {}})

    def upsert_group_origin(self, *, group_id: str, unified_msg_origin: str, last_active_at: int) -> None:
        if not group_id or not unified_msg_origin:
            return

        payload = self._read_raw()
        groups = payload.setdefault("groups", {})
        groups[str(group_id)] = {
            "unified_msg_origin": str(unified_msg_origin),
            "last_active_at": int(last_active_at),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._write_raw(payload)

    def list_group_records(self) -> list[GroupOriginRecord]:
        payload = self._read_raw()
        groups = payload.get("groups", {})
        if not isinstance(groups, dict):
            return []

        records: list[GroupOriginRecord] = []
        for gid, data in groups.items():
            if not isinstance(data, dict):
                continue
            records.append(
                GroupOriginRecord(
                    group_id=str(gid),
                    unified_msg_origin=str(data.get("unified_msg_origin", "")),
                    last_active_at=int(data.get("last_active_at", 0)),
                    updated_at=str(data.get("updated_at", "")),
                )
            )

        records.sort(key=lambda item: item.group_id)
        return records

    def _read_raw(self) -> dict:
        try:
            text = self.file_path.read_text(encoding="utf-8")
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
            return {"groups": {}}
        except (FileNotFoundError, json.JSONDecodeError):
            return {"groups": {}}

    def _write_raw(self, payload: dict) -> None:
        self.file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
