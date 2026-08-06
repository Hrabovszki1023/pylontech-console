from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pylontech_console.config import WebSettings
from pylontech_console.outputs.api.query import StateQuery
from pylontech_console.outputs.web.query import WebQuery
from pylontech_console.version import BuildIdentity, load_build_identity

WEB_ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=WEB_ROOT / "templates")


def encode_test_id_component(value: str) -> str:
    """Encode device identity as one reversible test-ID component."""
    allowed = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_."
    return "".join(
        chr(byte) if byte in allowed else f"%{byte:02X}"
        for byte in value.encode("utf-8")
    )


templates.env.filters["testid"] = encode_test_id_component


def create_web_router(
    query: StateQuery,
    settings: WebSettings,
    identity: BuildIdentity,
) -> APIRouter:
    web_query = WebQuery(query, settings)
    router = APIRouter(include_in_schema=False)

    @router.get("/", response_class=HTMLResponse)
    def rack_overview(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "rack.html",
            {"page": web_query.rack_page(), "app_identity": identity},
        )

    @router.get(
        "/web/fragments/overview",
        response_class=HTMLResponse,
    )
    def rack_overview_fragment(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "fragments/rack_content.html",
            {"page": web_query.rack_page()},
        )

    @router.get(
        "/modules/{barcode}",
        response_class=HTMLResponse,
    )
    def module_detail(request: Request, barcode: str) -> HTMLResponse:
        page = web_query.module_page(barcode)
        if page is None:
            raise HTTPException(status_code=404, detail="module not found")
        return templates.TemplateResponse(
            request,
            "module.html",
            {"page": page, "app_identity": identity},
        )

    @router.get(
        "/web/fragments/modules/{barcode}",
        response_class=HTMLResponse,
    )
    def module_detail_fragment(
        request: Request,
        barcode: str,
    ) -> HTMLResponse:
        page = web_query.module_page(barcode)
        if page is None:
            raise HTTPException(status_code=404, detail="module not found")
        return templates.TemplateResponse(
            request,
            "fragments/module_content.html",
            {"page": page},
        )

    return router


def mount_web(
    app: FastAPI,
    query: StateQuery,
    settings: WebSettings | None = None,
    identity: BuildIdentity | None = None,
) -> None:
    """Mount the read-only web adapter and its local assets."""
    app.mount(
        "/assets",
        StaticFiles(directory=WEB_ROOT / "static"),
        name="web-assets",
    )
    app.include_router(
        create_web_router(
            query,
            settings or WebSettings(),
            identity or load_build_identity(),
        ),
    )
