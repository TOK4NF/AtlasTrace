from __future__ import annotations

from hashlib import sha1
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
import json
import os

from atlastrace.services.common import get_case_or_raise, touch_case
from atlastrace.services.entities import add_entity, link_entities
from atlastrace.storage import Database
from atlastrace.utils import utc_now


def _insert_artifact(db: Database, case_id: int, *, kind: str, label: str, metadata: dict) -> dict:
    artifact_id = db.execute(
        """
        INSERT INTO artifacts(case_id, kind, label, path, sha256, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            case_id,
            kind,
            label,
            None,
            None,
            json.dumps(metadata, ensure_ascii=True, sort_keys=True),
            utc_now(),
        ),
    )
    row = db.fetchone("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
    return dict(row)


def check_hibp_account(
    db: Database,
    settings,
    case_slug: str,
    account: str,
    *,
    truncate_response: bool = False,
) -> dict:
    case = get_case_or_raise(db, case_slug)
    api_key = os.getenv("HIBP_API_KEY")
    if not api_key:
        raise RuntimeError("HIBP_API_KEY is required for account breach lookups.")

    encoded = quote(account, safe="")
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{encoded}?truncateResponse={'true' if truncate_response else 'false'}"
    request = Request(
        url,
        headers={
            "hibp-api-key": api_key,
            "user-agent": settings.user_agent,
            "accept": "application/json",
        },
    )

    breaches: list[dict] = []
    status = "ok"
    try:
        with urlopen(request, timeout=20) as response:
            breaches = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            breaches = []
        else:
            raise

    account_kind = "email" if "@" in account else "account"
    account_entity = add_entity(
        db,
        case_slug,
        account_kind,
        account,
        source="hibp_account",
        confidence=0.95,
    )

    for breach in breaches:
        name = breach.get("Name") or breach.get("Title") or "unknown-breach"
        breach_entity = add_entity(
            db,
            case_slug,
            "breach",
            name,
            name=name,
            source="hibp_account",
            confidence=0.85,
            metadata=breach,
        )
        link_entities(
            db,
            case_slug,
            int(account_entity["id"]),
            int(breach_entity["id"]),
            "appears_in_breach",
            source="hibp_account",
        )

    artifact = _insert_artifact(
        db,
        int(case["id"]),
        kind="breach_check",
        label=account,
        metadata={
            "provider": "Have I Been Pwned",
            "account": account,
            "breach_count": len(breaches),
            "results": breaches,
            "truncate_response": truncate_response,
        },
    )
    touch_case(db, case_slug)
    return {"artifact": artifact, "breach_count": len(breaches), "results": breaches, "status": status}


def check_pwned_password(
    db: Database,
    settings,
    case_slug: str,
    *,
    password: str | None = None,
    password_sha1: str | None = None,
) -> dict:
    case = get_case_or_raise(db, case_slug)
    if not password and not password_sha1:
        raise ValueError("Provide a password or a SHA1 hash.")

    full_sha1 = (password_sha1 or sha1(password.encode("utf-8")).hexdigest()).upper()
    if len(full_sha1) != 40:
        raise ValueError("The SHA1 hash must be 40 hexadecimal characters.")

    prefix = full_sha1[:5]
    suffix = full_sha1[5:]
    request = Request(
        f"https://api.pwnedpasswords.com/range/{prefix}",
        headers={
            "user-agent": settings.user_agent,
            "Add-Padding": "true",
        },
    )

    try:
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise RuntimeError(f"Pwned Passwords request failed with HTTP {exc.code}.") from exc

    count = 0
    for line in body.splitlines():
        if ":" not in line:
            continue
        candidate_suffix, candidate_count = line.split(":", 1)
        if candidate_suffix.strip().upper() == suffix:
            count = int(candidate_count.strip())
            break

    artifact = _insert_artifact(
        db,
        int(case["id"]),
        kind="password_check",
        label="pwned-passwords",
        metadata={
            "provider": "Have I Been Pwned Pwned Passwords",
            "hash_prefix": prefix,
            "matched": count > 0,
            "count": count,
        },
    )
    touch_case(db, case_slug)
    return {"artifact": artifact, "matched": count > 0, "count": count, "hash_prefix": prefix}
