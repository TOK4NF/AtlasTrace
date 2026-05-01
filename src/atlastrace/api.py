from __future__ import annotations

from atlastrace.plugins.registry import discover_modules
from atlastrace.services import (
    add_entity,
    create_case,
    export_markdown_report,
    get_case,
    list_cases,
    list_entities,
)
from atlastrace.settings import Settings
from atlastrace.storage import Database


def create_app(settings: Settings | None = None):
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI is not installed. Run: pip install -e .[api]"
        ) from exc

    resolved = settings or Settings.from_env()
    resolved.ensure_home()
    db = Database(resolved.db_path)
    db.ensure_schema()

    app = FastAPI(
        title="AtlasTrace API",
        version="0.1.0",
        description="Passive OSINT investigation API for cases, entities, and exports.",
    )

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/modules")
    def modules():
        return [module.__dict__ for module in discover_modules()]

    @app.get("/cases")
    def cases():
        return list_cases(db)

    @app.post("/cases")
    def cases_create(payload: dict):
        try:
            return create_case(
                db,
                resolved,
                title=payload["title"],
                slug=payload.get("slug"),
                description=payload.get("description", ""),
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/cases/{case_slug}")
    def case_detail(case_slug: str):
        try:
            case = get_case(db, case_slug)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        case["entities"] = list_entities(db, case_slug)
        return case

    @app.post("/cases/{case_slug}/entities")
    def case_add_entity(case_slug: str, payload: dict):
        try:
            return add_entity(
                db,
                case_slug,
                kind=payload["kind"],
                value=payload["value"],
                name=payload.get("name"),
                source=payload.get("source", "api"),
                confidence=float(payload.get("confidence", 0.5)),
                metadata=payload.get("metadata"),
            )
        except (KeyError, LookupError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/cases/{case_slug}/report")
    def case_report(case_slug: str):
        try:
            return export_markdown_report(db, resolved, case_slug)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn is not installed. Run: pip install -e .[api]") from exc

    uvicorn.run(create_app(), host=host, port=port)

