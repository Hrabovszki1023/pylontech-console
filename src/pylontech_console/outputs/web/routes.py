from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pylontech_console.outputs.api.query import StateQuery
from pylontech_console.outputs.web.query import WebQuery

WEB_ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=WEB_ROOT / "templates")


def create_web_router(query: StateQuery) -> APIRouter:
    web_query = WebQuery(query)
    router = APIRouter(include_in_schema=False)

    @router.get("/", response_class=HTMLResponse)
    def rack_overview(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "rack.html",
            {"page": web_query.rack_page()},
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
            {"page": page},
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


def mount_web(app: FastAPI, query: StateQuery) -> None:
    """Mount the read-only web adapter and its local assets."""
    app.mount(
        "/assets",
        StaticFiles(directory=WEB_ROOT / "static"),
        name="web-assets",
    )
    app.include_router(create_web_router(query))
