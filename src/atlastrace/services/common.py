from __future__ import annotations

from pathlib import Path

from atlastrace.settings import Settings
from atlastrace.storage import Database
from atlastrace.utils import ensure_directory, utc_now


def get_case_or_raise(db: Database, case_slug: str):
    row = db.fetchone("SELECT * FROM cases WHERE slug = ?", (case_slug,))
    if row is None:
        raise LookupError(f"Case not found: {case_slug}")
    return row


def resolve_case_id(db: Database, case_slug: str) -> int:
    return int(get_case_or_raise(db, case_slug)["id"])


def touch_case(db: Database, case_slug: str) -> None:
    db.execute(
        "UPDATE cases SET updated_at = ? WHERE slug = ?",
        (utc_now(), case_slug),
    )


def case_path(settings: Settings, case_slug: str, *parts: str) -> Path:
    base = ensure_directory(settings.case_root / case_slug)
    current = base
    for part in parts:
        current = current / part
    if parts:
        ensure_directory(current)
    return current
