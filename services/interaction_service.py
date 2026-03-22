from __future__ import annotations


class InteractionService:
    """处理 LLM 生成的主动发言文案（清洗与兜底）。"""

    def finalize_suggested_reply(self, raw_text: str) -> str:
        text = str(raw_text or "").strip()
        if not text:
            return "（未生成主动发言文案）"

        # 去掉常见引号包裹，避免模型输出带多余符号。
        if len(text) >= 2 and text[0] in {'"', "'", "“", "‘"} and text[-1] in {'"', "'", "”", "’"}:
            text = text[1:-1].strip()

        return text or "（未生成主动发言文案）"
