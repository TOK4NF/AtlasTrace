from __future__ import annotations

from pathlib import Path
import json

from atlastrace.services.cases import get_case
from atlastrace.services.common import case_path
from atlastrace.storage import Database
from atlastrace.utils import ensure_directory


def _build_markdown(case: dict, findings: list[dict], min_sources: int) -> str:
    lines = [
        f"# Correlation Report: {case['title']}",
        "",
        f"- Case slug: `{case['slug']}`",
        f"- Minimum distinct sources: `{min_sources}`",
        f"- Findings: `{len(findings)}`",
        "",
        "## Repeated Observables",
        "",
    ]

    if not findings:
        lines.append("- No cross-source correlations found with the current threshold.")
        lines.append("")
        return "\n".join(lines)

    for finding in findings:
        lines.append(
            f"- [{finding['kind']}] `{finding['value']}` found in {finding['source_count']} sources"
        )
        lines.append(f"  Sources: {', '.join(finding['sources'])}")
        if finding["artifact_labels"]:
            lines.append(f"  Artifacts: {', '.join(finding['artifact_labels'])}")
    lines.append("")
    return "\n".join(lines)


def correlate_case(
    db: Database,
    settings,
    case_slug: str,
    *,
    min_sources: int = 2,
    output: str | None = None,
) -> dict:
    case = get_case(db, case_slug)
    rows = db.fetchall(
        """
        SELECT
            e.id AS entity_id,
            e.kind AS kind,
            e.name AS name,
            e.value AS value,
            o.source AS observation_source,
            a.label AS artifact_label
        FROM observations o
        JOIN entities e ON e.id = o.entity_id
        LEFT JOIN artifacts a ON a.id = o.artifact_id
        WHERE o.case_id = ?
        ORDER BY e.kind ASC, e.value ASC, o.source ASC
        """,
        (case["id"],),
    )

    grouped: dict[int, dict] = {}
    for row in rows:
        entity_id = int(row["entity_id"])
        bucket = grouped.setdefault(
            entity_id,
            {
                "entity_id": entity_id,
                "kind": row["kind"],
                "name": row["name"],
                "value": row["value"],
                "sources": set(),
                "artifact_labels": set(),
            },
        )
        bucket["sources"].add(row["observation_source"])
        if row["artifact_label"]:
            bucket["artifact_labels"].add(row["artifact_label"])

    findings = []
    for item in grouped.values():
        source_list = sorted(item["sources"])
        if len(source_list) < min_sources:
            continue
        findings.append(
            {
                "entity_id": item["entity_id"],
                "kind": item["kind"],
                "name": item["name"],
                "value": item["value"],
                "source_count": len(source_list),
                "sources": source_list,
                "artifact_labels": sorted(item["artifact_labels"]),
            }
        )

    findings.sort(key=lambda value: (-value["source_count"], value["kind"], value["value"]))
    report_markdown = _build_markdown(case, findings, min_sources)

    if output:
        target = Path(output).resolve()
    else:
        target = case_path(settings, case_slug, "reports") / "correlation-report.md"
    ensure_directory(target.parent)

    if target.suffix.lower() == ".json":
        target.write_text(
            json.dumps({"case": case_slug, "min_sources": min_sources, "findings": findings}, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    else:
        target.write_text(report_markdown, encoding="utf-8")

    return {
        "case_slug": case_slug,
        "finding_count": len(findings),
        "path": str(target),
        "findings": findings,
    }

