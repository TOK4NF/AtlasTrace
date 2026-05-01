from __future__ import annotations

import argparse
import getpass

from atlastrace.api import serve
from atlastrace.plugins.registry import discover_modules
from atlastrace.services import (
    add_entity,
    add_note,
    archive_url,
    capture_web_page,
    check_hibp_account,
    check_pwned_password,
    correlate_case,
    create_case,
    export_markdown_report,
    export_mermaid_graph,
    import_document,
    inspect_media,
    link_entities,
    list_cases,
    list_entities,
    map_identity,
)
from atlastrace.services.ingest import IDENTITY_TEMPLATES
from atlastrace.settings import Settings
from atlastrace.storage import Database
from atlastrace.ui import print_error, print_json, print_line


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlastrace",
        description="Passive OSINT correlation multitool with identity, archive, and breach intelligence modules.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Create the local AtlasTrace workspace.")
    subparsers.add_parser("modules", help="List built-in and discovered modules.")
    subparsers.add_parser("case-list", help="List cases.")

    case_create = subparsers.add_parser("case-create", help="Create a new case.")
    case_create.add_argument("title")
    case_create.add_argument("--slug")
    case_create.add_argument("--description", default="")

    note_add = subparsers.add_parser("note-add", help="Add a note to a case.")
    note_add.add_argument("case_slug")
    note_add.add_argument("title")
    note_add.add_argument("body")

    entity_add = subparsers.add_parser("entity-add", help="Add an entity.")
    entity_add.add_argument("case_slug")
    entity_add.add_argument("kind")
    entity_add.add_argument("value")
    entity_add.add_argument("--name")
    entity_add.add_argument("--source", default="manual")
    entity_add.add_argument("--confidence", type=float, default=0.5)

    entity_list = subparsers.add_parser("entity-list", help="List case entities.")
    entity_list.add_argument("case_slug")

    link = subparsers.add_parser("link", help="Link two entities.")
    link.add_argument("case_slug")
    link.add_argument("from_entity_id", type=int)
    link.add_argument("to_entity_id", type=int)
    link.add_argument("label")
    link.add_argument("--source", default="manual")

    web_capture = subparsers.add_parser("web-capture", help="Capture a public web page.")
    web_capture.add_argument("case_slug")
    web_capture.add_argument("url")
    web_capture.add_argument("--label")

    doc_import = subparsers.add_parser("doc-import", help="Import a document into a case.")
    doc_import.add_argument("case_slug")
    doc_import.add_argument("path")
    doc_import.add_argument("--label")

    dataset_import = subparsers.add_parser("dataset-import", help="Import a dataset and keep it distinct for later correlation.")
    dataset_import.add_argument("case_slug")
    dataset_import.add_argument("path")
    dataset_import.add_argument("--label")

    correlate = subparsers.add_parser("correlate", help="Cross-reference repeated observables across sources.")
    correlate.add_argument("case_slug")
    correlate.add_argument("--min-sources", type=int, default=2)
    correlate.add_argument("--output")

    media_inspect = subparsers.add_parser("media-inspect", help="Inspect a media file.")
    media_inspect.add_argument("case_slug")
    media_inspect.add_argument("path")

    identity_map_cmd = subparsers.add_parser("identity-map", help="Map a handle to public profiles.")
    identity_map_cmd.add_argument("case_slug")
    identity_map_cmd.add_argument("handle")
    identity_map_cmd.add_argument(
        "--platforms",
        default=",".join(list(IDENTITY_TEMPLATES)),
        help="Comma-separated platform list.",
    )
    identity_map_cmd.add_argument("--fetch", action="store_true")

    breach_check = subparsers.add_parser("breach-check", help="Check an account against Have I Been Pwned.")
    breach_check.add_argument("case_slug")
    breach_check.add_argument("account")
    breach_check.add_argument("--full", action="store_true", help="Request the full breach payload when the API allows it.")

    password_check = subparsers.add_parser("password-check", help="Check a password against Pwned Passwords without storing the cleartext.")
    password_check.add_argument("case_slug")
    password_check.add_argument("--password")
    password_check.add_argument("--password-sha1")

    archive_cmd = subparsers.add_parser("archive", help="Prepare or submit an archive request.")
    archive_cmd.add_argument("case_slug")
    archive_cmd.add_argument("url")
    archive_cmd.add_argument("--submit", action="store_true")

    report_md = subparsers.add_parser("report-md", help="Export a Markdown case report.")
    report_md.add_argument("case_slug")
    report_md.add_argument("--output")

    report_graph = subparsers.add_parser("report-graph", help="Export a Mermaid graph.")
    report_graph.add_argument("case_slug")
    report_graph.add_argument("--output")

    serve_cmd = subparsers.add_parser("serve", help="Run the optional FastAPI service.")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", default=8000, type=int)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    settings.ensure_home()
    db = Database(settings.db_path)
    db.ensure_schema()

    try:
        if args.command == "init":
            print_line(f"AtlasTrace workspace initialized at {settings.home_dir}")
            return 0

        if args.command == "modules":
            print_json([module.__dict__ for module in discover_modules()])
            return 0

        if args.command == "case-list":
            print_json(list_cases(db))
            return 0

        if args.command == "case-create":
            print_json(
                create_case(
                    db,
                    settings,
                    args.title,
                    slug=args.slug,
                    description=args.description,
                )
            )
            return 0

        if args.command == "note-add":
            print_json(add_note(db, args.case_slug, args.title, args.body))
            return 0

        if args.command == "entity-add":
            print_json(
                add_entity(
                    db,
                    args.case_slug,
                    args.kind,
                    args.value,
                    name=args.name,
                    source=args.source,
                    confidence=args.confidence,
                )
            )
            return 0

        if args.command == "entity-list":
            print_json(list_entities(db, args.case_slug))
            return 0

        if args.command == "link":
            print_json(
                link_entities(
                    db,
                    args.case_slug,
                    args.from_entity_id,
                    args.to_entity_id,
                    args.label,
                    source=args.source,
                )
            )
            return 0

        if args.command == "web-capture":
            print_json(
                capture_web_page(
                    db,
                    settings,
                    args.case_slug,
                    args.url,
                    label=args.label,
                )
            )
            return 0

        if args.command == "doc-import":
            print_json(
                import_document(
                    db,
                    settings,
                    args.case_slug,
                    args.path,
                    label=args.label,
                    kind="document",
                )
            )
            return 0

        if args.command == "dataset-import":
            print_json(
                import_document(
                    db,
                    settings,
                    args.case_slug,
                    args.path,
                    label=args.label,
                    kind="dataset",
                )
            )
            return 0

        if args.command == "correlate":
            print_json(
                correlate_case(
                    db,
                    settings,
                    args.case_slug,
                    min_sources=args.min_sources,
                    output=args.output,
                )
            )
            return 0

        if args.command == "media-inspect":
            print_json(inspect_media(db, settings, args.case_slug, args.path))
            return 0

        if args.command == "identity-map":
            platforms = [item.strip() for item in args.platforms.split(",") if item.strip()]
            print_json(
                map_identity(
                    db,
                    settings,
                    args.case_slug,
                    args.handle,
                    platforms=platforms,
                    fetch=args.fetch,
                )
            )
            return 0

        if args.command == "breach-check":
            print_json(
                check_hibp_account(
                    db,
                    settings,
                    args.case_slug,
                    args.account,
                    truncate_response=not args.full,
                )
            )
            return 0

        if args.command == "password-check":
            if args.password and args.password_sha1:
                raise ValueError("Use either --password or --password-sha1, not both.")
            secret = args.password
            if not secret and not args.password_sha1:
                secret = getpass.getpass("Password to check: ")
            print_json(
                check_pwned_password(
                    db,
                    settings,
                    args.case_slug,
                    password=secret,
                    password_sha1=args.password_sha1,
                )
            )
            return 0

        if args.command == "archive":
            print_json(
                archive_url(
                    db,
                    settings,
                    args.case_slug,
                    args.url,
                    submit=args.submit,
                )
            )
            return 0

        if args.command == "report-md":
            result = export_markdown_report(
                db,
                settings,
                args.case_slug,
                output=args.output,
            )
            print_json({"path": result["path"]})
            return 0

        if args.command == "report-graph":
            result = export_mermaid_graph(
                db,
                settings,
                args.case_slug,
                output=args.output,
            )
            print_json({"path": result["path"]})
            return 0

        if args.command == "serve":
            serve(host=args.host, port=args.port)
            return 0

        parser.error(f"Unknown command: {args.command}")
        return 2
    except Exception as exc:
        print_error(f"AtlasTrace error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
