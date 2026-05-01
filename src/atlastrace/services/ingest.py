from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
import json
import mimetypes
import shutil

from atlastrace.analysis import extract_observables
from atlastrace.services.common import case_path, get_case_or_raise, touch_case
from atlastrace.services.entities import add_entity, link_entities, record_observables
from atlastrace.settings import Settings
from atlastrace.storage import Database
from atlastrace.utils import html_title, preview_text, safe_stem, sha256_file, utc_now

IDENTITY_TEMPLATES = {
    "github": "https://github.com/{handle}",
    "gitlab": "https://gitlab.com/{handle}",
    "bitbucket": "https://bitbucket.org/{handle}/",
    "x": "https://x.com/{handle}",
    "instagram": "https://www.instagram.com/{handle}/",
    "threads": "https://www.threads.net/@{handle}",
    "tiktok": "https://www.tiktok.com/@{handle}",
    "reddit": "https://www.reddit.com/user/{handle}/",
    "youtube": "https://www.youtube.com/@{handle}",
    "telegram": "https://t.me/{handle}",
    "mastodon": "https://mastodon.social/@{handle}",
    "linkedin": "https://www.linkedin.com/in/{handle}/",
    "bluesky": "https://bsky.app/profile/{handle}",
    "keybase": "https://keybase.io/{handle}",
    "steam": "https://steamcommunity.com/id/{handle}",
    "pinterest": "https://www.pinterest.com/{handle}/",
    "soundcloud": "https://soundcloud.com/{handle}",
    "medium": "https://medium.com/@{handle}",
    "devto": "https://dev.to/{handle}",
    "kaggle": "https://www.kaggle.com/{handle}",
    "dockerhub": "https://hub.docker.com/u/{handle}",
    "pypi": "https://pypi.org/user/{handle}/",
    "npm": "https://www.npmjs.com/~{handle}",
    "chesscom": "https://www.chess.com/member/{handle}",
    "flickr": "https://www.flickr.com/people/{handle}/",
    "vimeo": "https://vimeo.com/{handle}",
}


def _insert_artifact(
    db: Database,
    case_id: int,
    *,
    kind: str,
    label: str,
    path: str | None,
    sha256: str | None,
    metadata: dict,
) -> dict:
    artifact_id = db.execute(
        """
        INSERT INTO artifacts(case_id, kind, label, path, sha256, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            case_id,
            kind,
            label,
            path,
            sha256,
            json.dumps(metadata, ensure_ascii=True, sort_keys=True),
            utc_now(),
        ),
    )
    row = db.fetchone("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
    return dict(row)


def _insert_job(
    db: Database,
    case_id: int,
    *,
    module: str,
    target: str,
    status: str,
    result: dict,
) -> dict:
    job_id = db.execute(
        """
        INSERT INTO jobs(case_id, module, target, status, result_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            case_id,
            module,
            target,
            status,
            json.dumps(result, ensure_ascii=True, sort_keys=True),
            utc_now(),
        ),
    )
    row = db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
    return dict(row)


def _extract_html_text(html_text: str) -> str | None:
    try:
        import trafilatura
    except ImportError:
        return None

    try:
        return trafilatura.extract(
            html_text,
            output_format="txt",
            with_metadata=True,
            include_links=True,
        )
    except Exception:
        return None


def capture_web_page(
    db: Database,
    settings: Settings,
    case_slug: str,
    url: str,
    *,
    label: str | None = None,
) -> dict:
    case = get_case_or_raise(db, case_slug)
    request = Request(url, headers={"User-Agent": settings.user_agent})

    with urlopen(request, timeout=20) as response:
        payload = response.read()
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type", "")
        status = getattr(response, "status", 200)
        charset = response.headers.get_content_charset() or "utf-8"

    text = payload.decode(charset, errors="replace")
    title = html_title(text)
    extracted = _extract_html_text(text)
    basis = extracted or text
    observables = extract_observables(basis)

    hostname = urlparse(final_url).hostname or "capture"
    filename = f"{safe_stem(hostname)}-{utc_now().replace(':', '-')}.html"
    capture_path = case_path(settings, case_slug, "captures") / filename
    capture_path.write_bytes(payload)

    artifact = _insert_artifact(
        db,
        int(case["id"]),
        kind="web_capture",
        label=label or title or final_url,
        path=str(capture_path),
        sha256=sha256_file(capture_path),
        metadata={
            "content_type": content_type,
            "final_url": final_url,
            "status": status,
            "title": title,
            "text_preview": preview_text(extracted or text),
            "url": url,
        },
    )

    add_entity(
        db,
        case_slug,
        "url",
        final_url,
        source="web_capture",
        confidence=0.9,
    )
    if hostname:
        add_entity(
            db,
            case_slug,
            "domain",
            hostname,
            source="web_capture",
            confidence=0.8,
        )
    source_tag = f"web_capture:{safe_stem(hostname)}"
    record_observables(
        db,
        case_slug,
        observables,
        source=source_tag,
        confidence=0.45,
        artifact_id=int(artifact["id"]),
        context={"final_url": final_url, "title": title},
    )
    touch_case(db, case_slug)
    return {
        "artifact": artifact,
        "capture_path": str(capture_path),
        "final_url": final_url,
        "observable_count": len(observables),
        "status": status,
        "title": title,
    }


def import_document(
    db: Database,
    settings: Settings,
    case_slug: str,
    path: str,
    *,
    label: str | None = None,
    kind: str = "document",
) -> dict:
    case = get_case_or_raise(db, case_slug)
    source_path = Path(path).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    target_name = f"{utc_now().replace(':', '-')}-{source_path.name}"
    stored_path = case_path(settings, case_slug, "artifacts") / target_name
    shutil.copy2(source_path, stored_path)

    mime_type, _ = mimetypes.guess_type(str(source_path))
    text_preview = ""
    observables: list[dict[str, str]] = []

    if source_path.suffix.lower() in {".txt", ".md", ".json", ".csv", ".html", ".htm", ".py"}:
        raw_text = stored_path.read_text(encoding="utf-8", errors="replace")
        if source_path.suffix.lower() in {".html", ".htm"}:
            extracted = _extract_html_text(raw_text)
            text_preview = preview_text(extracted or raw_text)
            observables = extract_observables(extracted or raw_text)
        else:
            text_preview = preview_text(raw_text)
            observables = extract_observables(raw_text)

    artifact_label = label or source_path.name
    artifact = _insert_artifact(
        db,
        int(case["id"]),
        kind=kind,
        label=artifact_label,
        path=str(stored_path),
        sha256=sha256_file(stored_path),
        metadata={
            "artifact_label": artifact_label,
            "mime_type": mime_type or "application/octet-stream",
            "original_path": str(source_path),
            "size_bytes": stored_path.stat().st_size,
            "text_preview": text_preview,
        },
    )
    source_tag = f"{kind}:{safe_stem(label or source_path.stem)}"
    record_observables(
        db,
        case_slug,
        observables,
        source=source_tag,
        confidence=0.45,
        artifact_id=int(artifact["id"]),
        context={"artifact_label": artifact_label, "path": str(stored_path)},
    )
    touch_case(db, case_slug)
    return {
        "artifact": artifact,
        "observable_count": len(observables),
        "stored_path": str(stored_path),
    }


def map_identity(
    db: Database,
    settings: Settings,
    case_slug: str,
    handle: str,
    *,
    platforms: list[str] | None = None,
    fetch: bool = False,
) -> dict:
    case = get_case_or_raise(db, case_slug)
    normalized = handle.lstrip("@").strip()
    chosen = platforms or list(IDENTITY_TEMPLATES)

    handle_entity = add_entity(
        db,
        case_slug,
        "handle",
        normalized,
        source="identity_map",
        confidence=0.95,
    )

    findings = []
    for platform in chosen:
        template = IDENTITY_TEMPLATES.get(platform)
        if not template:
            continue

        candidate_url = template.format(handle=normalized)
        finding = {"platform": platform, "url": candidate_url}

        if fetch:
            request = Request(candidate_url, headers={"User-Agent": settings.user_agent})
            try:
                with urlopen(request, timeout=10) as response:
                    body = response.read(120_000).decode("utf-8", errors="replace")
                    finding["status"] = getattr(response, "status", 200)
                    finding["final_url"] = response.geturl()
                    finding["title"] = html_title(body)
            except Exception as exc:
                finding["status"] = "error"
                finding["error"] = str(exc)

        if finding.get("status") not in (None, "error") and int(finding["status"]) < 400:
            source_tag = f"identity_map:{platform}"
            profile = add_entity(
                db,
                case_slug,
                "profile_url",
                finding.get("final_url") or candidate_url,
                source=source_tag,
                confidence=0.55,
                metadata={"platform": platform},
            )
            link_entities(
                db,
                case_slug,
                int(handle_entity["id"]),
                int(profile["id"]),
                "appears_on",
                source=source_tag,
            )

        findings.append(finding)

    artifact = _insert_artifact(
        db,
        int(case["id"]),
        kind="identity_map",
        label=f"identity-map-{normalized}",
        path=None,
        sha256=None,
        metadata={
            "handle": normalized,
            "platform_count": len(findings),
            "results": findings,
        },
    )
    touch_case(db, case_slug)
    return {"artifact": artifact, "findings": findings}


def archive_url(
    db: Database,
    settings: Settings,
    case_slug: str,
    url: str,
    *,
    submit: bool = False,
) -> dict:
    case = get_case_or_raise(db, case_slug)
    encoded = quote(url, safe="")
    browse_url = f"https://web.archive.org/web/*/{url}"
    save_url = f"https://web.archive.org/save/{encoded}"

    status = "planned"
    archive_result = {"browse_url": browse_url, "save_url": save_url}

    if submit:
        request = Request(save_url, headers={"User-Agent": settings.user_agent})
        try:
            with urlopen(request, timeout=20) as response:
                archive_result["status_code"] = getattr(response, "status", 200)
                archive_result["final_url"] = response.geturl()
                status = "submitted"
        except Exception as exc:
            archive_result["error"] = str(exc)
            status = "error"

    artifact = _insert_artifact(
        db,
        int(case["id"]),
        kind="archive_request",
        label=url,
        path=None,
        sha256=None,
        metadata=archive_result,
    )
    _insert_job(
        db,
        int(case["id"]),
        module="archive",
        target=url,
        status=status,
        result=archive_result,
    )
    add_entity(
        db,
        case_slug,
        "url",
        url,
        source="archive",
        confidence=0.8,
    )
    if archive_result.get("final_url"):
        add_entity(
            db,
            case_slug,
            "archive_url",
            archive_result["final_url"],
            source="archive",
            confidence=0.8,
        )
    touch_case(db, case_slug)
    return {"artifact": artifact, "result": archive_result, "status": status}
