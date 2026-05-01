from __future__ import annotations

import json

from atlastrace.services.common import get_case_or_raise, touch_case
from atlastrace.storage import Database
from atlastrace.utils import utc_now


def add_entity(
    db: Database,
    case_slug: str,
    kind: str,
    value: str,
    *,
    name: str | None = None,
    source: str = "manual",
    confidence: float = 0.5,
    metadata: dict | None = None,
) -> dict:
    case = get_case_or_raise(db, case_slug)
    existing = db.fetchone(
        """
        SELECT * FROM entities
        WHERE case_id = ? AND kind = ? AND value = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (case["id"], kind, value),
    )
    if existing is not None:
        return dict(existing)

    entity_id = db.execute(
        """
        INSERT INTO entities(case_id, kind, name, value, confidence, source, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            case["id"],
            kind,
            name or value,
            value,
            confidence,
            source,
            json.dumps(metadata or {}, ensure_ascii=True, sort_keys=True),
            utc_now(),
        ),
    )
    touch_case(db, case_slug)
    row = db.fetchone("SELECT * FROM entities WHERE id = ?", (entity_id,))
    return dict(row)


def add_observation(
    db: Database,
    case_slug: str,
    entity_id: int,
    *,
    source: str,
    artifact_id: int | None = None,
    context: dict | None = None,
) -> dict:
    case = get_case_or_raise(db, case_slug)
    existing = db.fetchone(
        """
        SELECT * FROM observations
        WHERE case_id = ?
          AND entity_id = ?
          AND source = ?
          AND COALESCE(artifact_id, 0) = COALESCE(?, 0)
        LIMIT 1
        """,
        (case["id"], entity_id, source, artifact_id),
    )
    if existing is not None:
        return dict(existing)

    observation_id = db.execute(
        """
        INSERT INTO observations(case_id, entity_id, source, artifact_id, context_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            case["id"],
            entity_id,
            source,
            artifact_id,
            json.dumps(context or {}, ensure_ascii=True, sort_keys=True),
            utc_now(),
        ),
    )
    row = db.fetchone("SELECT * FROM observations WHERE id = ?", (observation_id,))
    return dict(row)


def list_entities(db: Database, case_slug: str) -> list[dict]:
    case = get_case_or_raise(db, case_slug)
    rows = db.fetchall(
        """
        SELECT * FROM entities
        WHERE case_id = ?
        ORDER BY kind ASC, name ASC, id ASC
        """,
        (case["id"],),
    )
    return [dict(row) for row in rows]


def link_entities(
    db: Database,
    case_slug: str,
    from_entity_id: int,
    to_entity_id: int,
    label: str,
    *,
    source: str = "manual",
) -> dict:
    case = get_case_or_raise(db, case_slug)
    relationship_id = db.execute(
        """
        INSERT INTO relationships(case_id, from_entity_id, to_entity_id, label, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            case["id"],
            from_entity_id,
            to_entity_id,
            label,
            source,
            utc_now(),
        ),
    )
    touch_case(db, case_slug)
    row = db.fetchone("SELECT * FROM relationships WHERE id = ?", (relationship_id,))
    return dict(row)


def record_observables(
    db: Database,
    case_slug: str,
    observables: list[dict[str, str]],
    *,
    source: str,
    confidence: float = 0.45,
    artifact_id: int | None = None,
    context: dict | None = None,
) -> list[dict]:
    created: list[dict] = []
    for item in observables:
        entity = add_entity(
            db,
            case_slug,
            item["kind"],
            item["value"],
            source=source,
            confidence=confidence,
            metadata=item.get("metadata"),
        )
        add_observation(
            db,
            case_slug,
            int(entity["id"]),
            source=source,
            artifact_id=artifact_id,
            context=context,
        )
        created.append(entity)
    return created
