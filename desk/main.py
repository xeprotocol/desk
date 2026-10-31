"""FastAPI application: JSON API under /v1, server-rendered pages elsewhere, one app behind two hosts."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__, og
from .api import agent, authn, public, reporter, team
from .config import lint_public_copy, strip_template
from .context import get_context
from .db import session
from .mirror import MarkdownMirror
from .ui import render
from .ui import router as ui_router

log = logging.getLogger("desk.app")
HERE = Path(__file__).parent


def template_texts() -> list[str]:
    return [strip_template(p.read_text(encoding="utf-8")) for p in (HERE / "templates").rglob("*.html")]


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = get_context()
    logging.basicConfig(
        level=getattr(logging, ctx.settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    await ctx.refresh_node()
    violations = lint_public_copy(ctx.config, template_texts())
    app.state.copy_violations = violations
    if violations:
        log.warning("public copy lint: %d violation(s): %s", len(violations), violations[:5])
    if not ctx.vault.available:
        log.warning("vault key not loaded: private reports cannot be stored or read")
    try:
        async with session() as db:
            await ctx.events.append(
                db,
                "api.started",
                "desk",
                {
                    "version": __version__,
                    "network_id": ctx.node.network_id,
                    "git_commit": ctx.settings.git_commit,
                    "config_hashes": ctx.config.hashes,
                    "copy_lint_violations": len(violations),
                    "hosts": ctx.settings.hosts,
                    "vault": ctx.vault.available,
                },
            )
            await db.commit()
    except Exception as e:
        log.warning("could not write api.started (database not ready?): %s", e)
    yield
    await ctx.aclose()


app = FastAPI(
    title="XE Desk",
    version=__version__,
    lifespan=lifespan,
    docs_url="/v1/docs",
    openapi_url="/v1/openapi.json",
)

app.include_router(public.router)
app.include_router(agent.router)
app.include_router(team.router)
app.include_router(authn.router)
app.include_router(reporter.router)
app.include_router(og.router)
app.include_router(ui_router)
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
app.add_middleware(MarkdownMirror, base_url="")


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/v1"):
        return JSONResponse(
            {"error": exc.detail, "status": exc.status_code},
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )
    return render(
        request, "error.html", {"status": exc.status_code, "detail": exc.detail}, status_code=exc.status_code
    )


@app.exception_handler(Exception)
async def any_error(request: Request, exc: Exception):
    """No bare 500s (the #101 lesson): a JSON or page error with no stack trace."""
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    if request.url.path.startswith("/v1"):
        return JSONResponse({"error": "internal error", "status": 500}, status_code=500)
    return render(
        request,
        "error.html",
        {"status": 500, "detail": "The desk hit an error. It is logged."},
        status_code=500,
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith("/v1"):
        resp.headers.setdefault("Access-Control-Allow-Origin", "*")
        resp.headers.setdefault("Access-Control-Allow-Headers", "Authorization, Content-Type")
        resp.headers.setdefault("Cache-Control", "no-store")
    elif request.url.path.startswith("/static"):
        # URLs carry a content hash (ui.ASSET_V), so a file may be kept for good; a change is a new URL
        resp.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    else:
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' https: data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


@app.options("/v1/{rest:path}", include_in_schema=False)
async def cors_preflight(rest: str):
    return JSONResponse(
        {},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Desk-CSRF",
        },
    )
