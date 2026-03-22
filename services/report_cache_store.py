from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class ReportCacheRecord:
    group_id: str
    date: str
    mode: str
    window_start: int
    window_end: int
    generated_at: str
    last_message_timestamp: int
    message_count: int
    provider_id: str
    analysis_provider_notice: str
    max_messages_for_analysis: int
    prompt_signature: str
    cache_version: int
    source: str
    report: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReportCacheRecord":
        return cls(
            group_id=str(data.get("group_id", "")),
            date=str(data.get("date", "")),
            mode=str(data.get("mode", "")),
            window_start=int(data.get("window_start", 0)),
            window_end=int(data.get("window_end", 0)),
            generated_at=str(data.get("generated_at", "")),
            last_message_timestamp=int(data.get("last_message_timestamp", 0)),
            message_count=int(data.get("message_count", 0)),
            provider_id=str(data.get("provider_id", "")),
            analysis_provider_notice=str(data.get("analysis_provider_notice", "")),
            max_messages_for_analysis=int(data.get("max_messages_for_analysis", 0)),
            prompt_signature=str(data.get("prompt_signature", "")),
            cache_version=int(data.get("cache_version", 0)),
            source=str(data.get("source", "")),
            report=data.get("report", {}) if isinstance(data.get("report", {}), dict) else {},
        )


class ReportCacheStore:
    def __init__(self, file_path: Path, cache_version: int = 1):
        self.file_path = file_path
        self.cache_version = int(cache_version)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write_raw({"cache_version": self.cache_version, "entries": {}})

    def get_record(self, *, group_id: str, date: str, mode: str) -> ReportCacheRecord | None:
        payload = self._read_raw()
        entries = payload.get("entries", {})
        if not isinstance(entries, dict):
            return None

        key = self._build_key(group_id=group_id, date=date, mode=mode)
        raw = entries.get(key)
        if not isinstance(raw, dict):
            return None

        record = ReportCacheRecord.from_dict(raw)
        if record.cache_version != self.cache_version:
            return None
        return record

    def upsert_record(self, record: ReportCacheRecord) -> None:
        payload = self._read_raw()
        entries = payload.setdefault("entries", {})
        if not isinstance(entries, dict):
            entries = {}
            payload["entries"] = entries

        key = self._build_key(group_id=record.group_id, date=record.date, mode=record.mode)
        entries[key] = record.to_dict()
        payload["cache_version"] = self.cache_version
        self._write_raw(payload)

    def _build_key(self, *, group_id: str, date: str, mode: str) -> str:
        return f"{group_id}::{date}::{mode}"

    def _read_raw(self) -> dict[str, Any]:
        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {"cache_version": self.cache_version, "entries": {}}
            return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {"cache_version": self.cache_version, "entries": {}}

    def _write_raw(self, payload: dict[str, Any]) -> None:
        self.file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
