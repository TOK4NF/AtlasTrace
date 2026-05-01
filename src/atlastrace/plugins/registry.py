from __future__ import annotations

from importlib.metadata import entry_points

from atlastrace.plugins.base import ModuleInfo


BUILTIN_MODULES = [
    ModuleInfo(
        name="caseboard",
        summary="Create cases, notes, evidence records, and exports.",
        safety="local data only",
        outputs="SQLite rows, Markdown reports, Mermaid graphs",
    ),
    ModuleInfo(
        name="web_capture",
        summary="Passively fetch a public page, preserve HTML, and extract observables.",
        safety="public HTTP fetch only",
        outputs="raw HTML capture, extracted text preview, entities",
        optional_dependencies="trafilatura",
    ),
    ModuleInfo(
        name="documents",
        summary="Import text-ish files, hash them, and extract URLs, domains, emails, and IPv4 values.",
        safety="user-supplied files only",
        outputs="artifact records, observables",
        optional_dependencies="trafilatura",
    ),
    ModuleInfo(
        name="correlation",
        summary="Cross-reference repeated observables across multiple imported sources and artifacts.",
        safety="user-supplied files and passive observations only",
        outputs="correlation report, repeated observables, source overlap",
    ),
    ModuleInfo(
        name="media",
        summary="Inspect local media, optionally extract EXIF and OCR text.",
        safety="user-supplied files only",
        outputs="artifact records, metadata, OCR observables",
        optional_dependencies="exiftool, Pillow, pytesseract",
    ),
    ModuleInfo(
        name="identity_map",
        summary="Generate public profile candidates for a handle across many public services and optionally fetch page titles.",
        safety="public profile URLs only",
        outputs="artifact records, profile entities",
    ),
    ModuleInfo(
        name="breach_check",
        summary="Check an account or password against Have I Been Pwned style breach intelligence.",
        safety="official passive breach APIs only",
        outputs="breach artifacts, linked breach entities, password exposure count",
    ),
    ModuleInfo(
        name="archive",
        summary="Prepare archive endpoints and optional Save Page Now submission.",
        safety="public archive interaction only",
        outputs="artifact records, archive URLs",
    ),
]


def discover_modules() -> list[ModuleInfo]:
    modules = list(BUILTIN_MODULES)
    try:
        for entry_point in entry_points(group="atlastrace.modules"):
            loaded = entry_point.load()
            if isinstance(loaded, ModuleInfo):
                modules.append(loaded)
    except Exception:
        pass
    return modules
