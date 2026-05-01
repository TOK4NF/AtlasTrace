from __future__ import annotations

from atlastrace.services.common import case_path
from atlastrace.settings import Settings
from atlastrace.storage import Database
from atlastrace.utils import ensure_directory, slugify, utc_now


def create_case(
    db: Database,
    settings: Settings,
    title: str,
    slug: str | None = None,
    description: str = "",
):
    settings.ensure_home()
    case_slug = slugify(slug or title)
    if db.fetchone("SELECT 1 FROM cases WHERE slug = ?", (case_slug,)):
        raise ValueError(f"Case already exists: {case_slug}")

    timestamp = utc_now()
    db.execute(
        """
        INSERT INTO cases(slug, title, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (case_slug, title, description, timestamp, timestamp),
    )

    ensure_directory(case_path(settings, case_slug, "artifacts"))
    ensure_directory(case_path(settings, case_slug, "captures"))
    ensure_directory(case_path(settings, case_slug, "reports"))
    return get_case(db, case_slug)


def list_cases(db: Database) -> list[dict]:
    rows = db.fetchall(
        "SELECT * FROM cases ORDER BY updated_at DESC, created_at DESC"
    )
    return [dict(row) for row in rows]


def get_case(db: Database, case_slug: str) -> dict:
    row = db.fetchone("SELECT * FROM cases WHERE slug = ?", (case_slug,))
    if row is None:
        raise LookupError(f"Case not found: {case_slug}")
    return dict(row)


def add_note(db: Database, case_slug: str, title: str, body: str) -> dict:
    case = get_case(db, case_slug)
    created_at = utc_now()
    note_id = db.execute(
        """
        INSERT INTO notes(case_id, title, body, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (case["id"], title, body, created_at),
    )
    db.execute(
        "UPDATE cases SET updated_at = ? WHERE slug = ?",
        (created_at, case_slug),
    )
    row = db.fetchone("SELECT * FROM notes WHERE id = ?", (note_id,))
    return dict(row)

