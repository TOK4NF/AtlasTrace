from __future__ import annotations

from pathlib import Path
import json
import mimetypes
import shutil
import subprocess

from atlastrace.analysis import extract_observables
from atlastrace.services.common import case_path, get_case_or_raise, touch_case
from atlastrace.services.entities import record_observables
from atlastrace.storage import Database
from atlastrace.utils import preview_text, sha256_file, utc_now


def _insert_artifact_row(
    db: Database,
    case_id: int,
    *,
    kind: str,
    label: str,
    path: str,
    sha256: str,
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


def _run_exiftool(path: Path) -> dict | None:
    try:
        result = subprocess.run(
            ["exiftool", "-j", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    try:
        decoded = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not decoded:
        return None
    return decoded[0]


def _pillow_summary(path: Path) -> dict | None:
    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        with Image.open(path) as image:
            return {
                "format": image.format,
                "mode": image.mode,
                "width": image.width,
                "height": image.height,
            }
    except Exception:
        return None


def _ocr_text(path: Path) -> str | None:
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return None

    try:
        with Image.open(path) as image:
            return pytesseract.image_to_string(image)
    except Exception:
        return None


def inspect_media(db: Database, settings, case_slug: str, path: str) -> dict:
    case = get_case_or_raise(db, case_slug)
    source_path = Path(path).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    target_name = f"{utc_now().replace(':', '-')}-{source_path.name}"
    stored_path = case_path(settings, case_slug, "artifacts") / target_name
    shutil.copy2(source_path, stored_path)

    mime_type, _ = mimetypes.guess_type(str(source_path))
    metadata = {
        "mime_type": mime_type or "application/octet-stream",
        "original_path": str(source_path),
        "size_bytes": stored_path.stat().st_size,
    }

    exif_data = _run_exiftool(stored_path)
    if exif_data:
        metadata["exiftool"] = exif_data

    pillow_data = _pillow_summary(stored_path)
    if pillow_data:
        metadata["image"] = pillow_data

    ocr_text = _ocr_text(stored_path)
    if ocr_text:
        metadata["ocr_preview"] = preview_text(ocr_text)

    artifact = _insert_artifact_row(
        db,
        int(case["id"]),
        kind="media",
        label=source_path.name,
        path=str(stored_path),
        sha256=sha256_file(stored_path),
        metadata=metadata,
    )

    observable_input = ""
    if exif_data:
        observable_input += json.dumps(exif_data, ensure_ascii=True)
    if ocr_text:
        observable_input += "\n" + ocr_text

    observables = extract_observables(observable_input) if observable_input else []
    record_observables(
        db,
        case_slug,
        observables,
        source="media_inspect",
        confidence=0.4,
    )
    touch_case(db, case_slug)
    return {
        "artifact": artifact,
        "observable_count": len(observables),
        "stored_path": str(stored_path),
    }

