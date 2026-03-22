"""Tests for astrbot_plugin_group_digest."""

from __future__ import annotations

import logging
import sys
import types
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent
if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


if "astrbot.api" not in sys.modules:
    astrbot_module = types.ModuleType("astrbot")
    api_module = types.ModuleType("astrbot.api")
    event_module = types.ModuleType("astrbot.api.event")

    class MessageChain:
        def __init__(self):
            self._chunks: list[str] = []

        def message(self, text: str):
            self._chunks.append(str(text))
            return self

        def __str__(self) -> str:
            return "".join(self._chunks)

    api_module.logger = logging.getLogger("astrbot.tests")
    event_module.MessageChain = MessageChain
    api_module.event = event_module
    astrbot_module.api = api_module

    sys.modules["astrbot"] = astrbot_module
    sys.modules["astrbot.api"] = api_module
    sys.modules["astrbot.api.event"] = event_module
