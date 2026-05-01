from __future__ import annotations

from pathlib import Path
import json

from atlastrace.services.cases import get_case
from atlastrace.services.common import case_path
from atlastrace.storage import Database
from atlastrace.utils import ensure_directory


def _case_bundle(db: Database, case_slug: str) -> dict:
    case = get_case(db, case_slug)
    case_id = case["id"]
    notes = [dict(row) for row in db.fetchall("SELECT * FROM notes WHERE case_id = ? ORDER BY id ASC", (case_id,))]
    entities = [dict(row) for row in db.fetchall("SELECT * FROM entities WHERE case_id = ? ORDER BY id ASC", (case_id,))]
    relationships = [
        dict(row)
        for row in db.fetchall(
            "SELECT * FROM relationships WHERE case_id = ? ORDER BY id ASC",
            (case_id,),
        )
    ]
    artifacts = [
        dict(row)
        for row in db.fetchall(
            "SELECT * FROM artifacts WHERE case_id = ? ORDER BY id ASC",
            (case_id,),
        )
    ]
    jobs = [dict(row) for row in db.fetchall("SELECT * FROM jobs WHERE case_id = ? ORDER BY id ASC", (case_id,))]
    return {
        "case": case,
        "notes": notes,
        "entities": entities,
        "relationships": relationships,
        "artifacts": artifacts,
        "jobs": jobs,
    }


def _decode_metadata(row: dict) -> dict:
    raw = row.get("metadata_json") or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def render_markdown_report(bundle: dict) -> str:
    case = bundle["case"]
    lines = [
        f"# {case['title']}",
        "",
        f"- Slug: `{case['slug']}`",
        f"- Created: `{case['created_at']}`",
        f"- Updated: `{case['updated_at']}`",
        "",
    ]
    if case["description"]:
        lines.extend([case["description"], ""])

    lines.extend(
        [
            "## Overview",
            "",
            f"- Entities: {len(bundle['entities'])}",
            f"- Relationships: {len(bundle['relationships'])}",
            f"- Artifacts: {len(bundle['artifacts'])}",
            f"- Notes: {len(bundle['notes'])}",
            f"- Jobs: {len(bundle['jobs'])}",
            "",
            "## Entities",
            "",
        ]
    )

    if bundle["entities"]:
        for entity in bundle["entities"]:
            lines.append(
                f"- `#{entity['id']}` [{entity['kind']}] {entity['name']} -> `{entity['value']}` "
                f"(source: `{entity['source']}`, confidence: {entity['confidence']})"
            )
    else:
        lines.append("- No entities yet.")

    lines.extend(["", "## Relationships", ""])
    if bundle["relationships"]:
        entity_labels = {item["id"]: item["name"] for item in bundle["entities"]}
        for relationship in bundle["relationships"]:
            left = entity_labels.get(relationship["from_entity_id"], f"#{relationship['from_entity_id']}")
            right = entity_labels.get(relationship["to_entity_id"], f"#{relationship['to_entity_id']}")
            lines.append(
                f"- `{left}` -[{relationship['label']}]-> `{right}` (source: `{relationship['source']}`)"
            )
    else:
        lines.append("- No relationships yet.")

    lines.extend(["", "## Artifacts", ""])
    if bundle["artifacts"]:
        for artifact in bundle["artifacts"]:
            metadata = _decode_metadata(artifact)
            preview = metadata.get("text_preview") or metadata.get("ocr_preview") or ""
            path = artifact["path"] or "(virtual)"
            lines.append(
                f"- `#{artifact['id']}` [{artifact['kind']}] {artifact['label']} - `{path}`"
            )
            if preview:
                lines.append(f"  Preview: {preview}")
    else:
        lines.append("- No artifacts yet.")

    lines.extend(["", "## Notes", ""])
    if bundle["notes"]:
        for note in bundle["notes"]:
            lines.append(f"- **{note['title']}**: {note['body']}")
    else:
        lines.append("- No notes yet.")

    lines.extend(["", "## Jobs", ""])
    if bundle["jobs"]:
        for job in bundle["jobs"]:
            lines.append(
                f"- `#{job['id']}` [{job['module']}] target=`{job['target']}` status=`{job['status']}`"
            )
    else:
        lines.append("- No jobs yet.")

    lines.append("")
    return "\n".join(lines)


def render_mermaid_graph(bundle: dict) -> str:
    lines = ["graph TD"]
    for entity in bundle["entities"]:
        label = f"{entity['kind']}: {entity['name']}".replace('"', "'")
        lines.append(f'  E{entity["id"]}["{label}"]')

    if bundle["relationships"]:
        for relationship in bundle["relationships"]:
            edge = relationship["label"].replace('"', "'")
            lines.append(
                f'  E{relationship["from_entity_id"]} -->|"{edge}"| E{relationship["to_entity_id"]}'
            )
    return "\n".join(lines) + "\n"


def export_markdown_report(
    db: Database,
    settings,
    case_slug: str,
    output: str | None = None,
) -> dict:
    bundle = _case_bundle(db, case_slug)
    report = render_markdown_report(bundle)
    target = Path(output).resolve() if output else case_path(settings, case_slug, "reports") / "case-report.md"
    ensure_directory(target.parent)
    target.write_text(report, encoding="utf-8")
    return {"path": str(target), "content": report}


def export_mermaid_graph(
    db: Database,
    settings,
    case_slug: str,
    output: str | None = None,
) -> dict:
    bundle = _case_bundle(db, case_slug)
    graph = render_mermaid_graph(bundle)
    target = Path(output).resolve() if output else case_path(settings, case_slug, "reports") / "case-graph.mmd"
    ensure_directory(target.parent)
    target.write_text(graph, encoding="utf-8")
    return {"path": str(target), "content": graph}

