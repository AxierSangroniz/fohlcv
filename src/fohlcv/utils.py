from __future__ import annotations

def is_blank(s: str | None) -> bool:
    return s is None or not str(s).strip()
