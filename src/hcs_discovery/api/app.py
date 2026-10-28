"""FastAPI application factory."""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .. import CREDIT, PRODUCT_NAME, TAGLINE, __version__
from ..core.config import Settings, get_settings
from ..core.errors import AppError, PolicyError
from ..core.logging import configure_logging, correlation_id
from ..database.base import dispose_engines, get_session_factory, init_db
from ..workflow.registry import default_registry
from ..workflow.templates import templates
from .ratelimit import RateLimiter
from .routes import agent, compounds, connectors, datasets, models, projects, runs, system, workflows


def _resolve_web_dist() -> Path | None:
    """Prefer the SPA bundled in the wheel; fall back to a repo checkout."""
    packaged = Path(__file__).resolve().parents[1] / "web"
    if (packaged / "index.html").is_file():
        return packaged
    repo = Path(__file__).resolve().parents[3] / "apps" / "web" / "dist"
    if (repo / "index.html").is_file():
        return repo
    return None


WEB_DIST = _resolve_web_dist()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if not settings.is_loopback and not settings.api_token:
        raise PolicyError(
            "Refusing to bind to a non-loopback interface without HCS_API_TOKEN. Set a token or bind to 127.0.0.1."
        )
    configure_logging()
    settings.ensure_dirs()
    init_db(settings)

    app = FastAPI(
        title=f"{PRODUCT_NAME} API",
        version=__version__,
        description=f"{TAGLINE} Local-first, reproducible drug-discovery research workbench.",
        docs_url="/api/docs" if settings.is_loopback else None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )
    app.state.settings = settings
    app.state.session_factory = get_session_factory(settings)
    app.state.registry = default_registry()
    app.state.started_at = datetime.now(UTC)
    app.state.rate_limiter = RateLimiter(limit=60, window_seconds=60)

    if settings.is_loopback:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = correlation_id.set(request_id)
        try:
            if _needs_auth(request, settings) and not _authorised(request, settings):
                return JSONResponse(
                    status_code=401,
                    content={"error": {"code": "unauthorized", "message": "Valid bearer token required."}},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if _is_expensive(request) and not settings.is_loopback:
                client = request.client.host if request.client else "unknown"
                if not app.state.rate_limiter.allow(client):
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": {
                                "code": "rate_limited",
                                "message": "Too many requests; slow down.",
                            }
                        },
                    )
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; "
                "base-uri 'self'; form-action 'self'"
            )
            return response
        finally:
            correlation_id.reset(token)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            headers={"X-Request-ID": request.headers.get("x-request-id", "")},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request payload is invalid.",
                    "details": {"issues": exc.errors()},
                }
            },
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_handler(request: Request, exc: PydanticValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Payload failed schema validation.",
                    "details": {"issues": exc.errors(include_url=False)},
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "http_error", "message": str(exc.detail)}},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("hcs.api").exception("unhandled API error")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred. See local logs for a redacted traceback.",
                }
            },
        )

    for router in (
        system.router,
        projects.router,
        datasets.router,
        compounds.router,
        workflows.router,
        runs.router,
        models.router,
        connectors.router,
        agent.router,
    ):
        app.include_router(router)

    app.include_router(_meta_router())
    _mount_web(app)
    return app


def _meta_router():
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/v1", tags=["meta"])

    @router.get("/about")
    def about(request: Request) -> dict[str, Any]:
        return {
            "product": PRODUCT_NAME,
            "version": __version__,
            "tagline": TAGLINE,
            "credit": CREDIT,
            "license": "Apache-2.0 (project code; third-party components have their own licenses)",
            "local_first": True,
            "network_policy": request.app.state.settings.network_policy,
        }

    @router.get("/nodes")
    def nodes(request: Request) -> dict[str, Any]:
        return {"items": request.app.state.registry.catalog()}

    @router.get("/templates")
    def template_list() -> dict[str, Any]:
        return {"items": templates()}

    return router


def _needs_auth(request: Request, settings: Settings) -> bool:
    if settings.is_loopback or not settings.api_token:
        return False
    return request.url.path.startswith("/api/") and request.url.path not in {"/api/v1/health"}


def _authorised(request: Request, settings: Settings) -> bool:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return False
    return secrets.compare_digest(token, settings.api_token or "")


def _is_expensive(request: Request) -> bool:
    if request.method != "POST":
        return False
    path = request.url.path
    return path.endswith("/datasets") or path == "/api/v1/runs" or path.endswith("/compounds/validate")


def _mount_web(app: FastAPI) -> None:
    if WEB_DIST is None:
        return
    assets = WEB_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> Response:
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "not_found", "message": "Unknown route"}},
            )
        candidate = (WEB_DIST / full_path).resolve()
        if candidate.is_file() and WEB_DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")


def shutdown(app: FastAPI) -> None:  # pragma: no cover - lifecycle helper
    dispose_engines()
