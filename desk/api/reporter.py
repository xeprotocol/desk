"""The reporter side of /v1: sign in three ways, bind a payout address, file, follow, reply, withdraw.

Sessions are the `desk_reporter` cookie; browser writes carry `X-Desk-CSRF` like the team's. Every
route that touches a ticket checks ownership here, since the authorisation matrix only gives a reporter
read access to their own private tickets and nothing else.
"""

from __future__ import annotations

import secrets
import time
from collections import defaultdict
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import delete, select

from .. import auth
from ..canonical import DOMAIN_LOGIN, DOMAIN_PAYOUT
from ..models import Challenge, Reporter
from ..services import channels
from ..services import reporters as rsvc
from ..services import tickets as tsvc
from .deps import Ctx, Db, Who

router = APIRouter(prefix="/v1/reporter", tags=["reporter"])

_attempts: dict[str, list[float]] = defaultdict(list)
LIMIT, WINDOW = 12, 600
FILE_LIMIT, FILE_WINDOW = 6, 3600
_filings: dict[str, list[float]] = defaultdict(list)


def _limit(request: Request, table=_attempts, limit=LIMIT, window=WINDOW, what="attempts") -> None:
    ip = auth.client_ip(request) or "?"
    cut = time.time() - window
    hits = [t for t in table[ip] if t > cut]
    if len(hits) >= limit:
        raise HTTPException(429, f"too many {what} from this address; wait a while")
    hits.append(time.time())
    table[ip] = hits


def _reporter(who: Who, request: Request, *, write: bool = True) -> Reporter:
    if who.reporter is None or who.reporter_session is None:
        raise HTTPException(401, "sign in first")
    if write and request.method not in ("GET", "HEAD", "OPTIONS"):
        auth.check_csrf(request, who.reporter_session)
    return who.reporter


def _safe_next(ctx: Ctx, nxt: str | None, default: str = "/my") -> str:
    """A post-sign-in destination: a path on this deployment, or an absolute URL on one of its hosts."""
    if not nxt:
        return default
    if nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    u = urlsplit(nxt)
    if u.scheme == ctx.settings.scheme and u.hostname in ctx.settings.hosts.values():
        return nxt
    return default


async def _sign_in(ctx: Ctx, db, request: Request, response: Response, r: Reporter, how: str) -> dict:
    s, raw = await auth.create_reporter_session(db, r, how, request)
    await ctx.events.append(
        db, "reporter.login", f"reporter:{r.id}", {"how": how, "ip": auth.client_ip(request)}, public=False
    )
    await db.commit()
    auth.set_session_cookie(response, raw, ctx.settings, name=auth.REPORTER_COOKIE)
    return {"ok": True, "reporter": rsvc.to_dict(r), "csrf": s.csrf}


# ---- GitHub OAuth -----------------------------------------------------------------------------------


def _callback_url(ctx: Ctx) -> str:
    return f"{ctx.settings.scheme}://{ctx.settings.hosts['bounty']}/v1/reporter/auth/github/callback"


@router.get("/auth/github")
async def github_start(ctx: Ctx, db: Db, who: Who, request: Request, next: str | None = None):
    """Send the browser to GitHub. The state rides in `challenges` with where to come back to and, if a
    signed-in reporter is adding GitHub to their account, which account."""
    if not ctx.settings.github_oauth_client_id:
        raise HTTPException(503, "GitHub sign-in is not configured")
    _limit(request)
    state = secrets.token_urlsafe(24)
    db.add(
        Challenge(
            id=state,
            kind="oauth",
            user_id=None,
            challenge=b"",
            expires_at=auth.now() + auth.CHALLENGE_TTL,
            detail={"next": _safe_next(ctx, next), "link_to": who.reporter.id if who.reporter else None},
        )
    )
    await db.commit()
    q = urlencode(
        {
            "client_id": ctx.settings.github_oauth_client_id,
            "redirect_uri": _callback_url(ctx),
            "scope": "read:user user:email",
            "state": state,
            "allow_signup": "true",
        }
    )
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{q}", status_code=302)


@router.get("/auth/github/callback")
async def github_callback(
    ctx: Ctx, db: Db, request: Request, code: str = "", state: str = "", error: str = ""
):
    ch = (await db.execute(select(Challenge).where(Challenge.id == state))).scalar_one_or_none()
    if ch is None or ch.kind != "oauth" or ch.expires_at < auth.now():
        raise HTTPException(400, "sign-in expired or state mismatch; start again")
    await db.execute(delete(Challenge).where(Challenge.id == state))
    if error or not code:
        raise HTTPException(400, f"GitHub did not sign you in: {error or 'no code'}")
    async with httpx.AsyncClient(timeout=15) as client:
        tok = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": ctx.settings.github_oauth_client_id,
                "client_secret": ctx.settings.github_oauth_client_secret,
                "code": code,
                "redirect_uri": _callback_url(ctx),
            },
        )
        is_json = tok.headers.get("content-type", "").startswith("application/json")
        access = (tok.json() if is_json else {}).get("access_token")
        if not access:
            raise HTTPException(400, "GitHub did not return a token; start again")
        h = {"Authorization": f"Bearer {access}", "Accept": "application/vnd.github+json"}
        user = (await client.get("https://api.github.com/user", headers=h)).json()
        email = ""
        try:
            emails = (await client.get("https://api.github.com/user/emails", headers=h)).json()
            primary = [e for e in emails if e.get("primary") and e.get("verified")]
            email = (primary or [{}])[0].get("email") or ""
        except Exception:
            email = ""
    if not isinstance(user, dict) or "id" not in user:
        raise HTTPException(400, "GitHub returned no user; start again")
    link_to = await rsvc.get(db, ch.detail.get("link_to")) if ch.detail.get("link_to") else None
    r = await rsvc.from_github(ctx, db, user, email, link_to=link_to)
    resp = RedirectResponse(ch.detail.get("next") or "/my", status_code=302)
    await _sign_in(ctx, db, request, resp, r, "github")
    return resp


# ---- Discord OAuth ------------------------------------------------------------------------------------


def _discord_callback_url(ctx: Ctx) -> str:
    return f"{ctx.settings.scheme}://{ctx.settings.hosts['bounty']}/v1/reporter/auth/discord/callback"


@router.get("/auth/discord")
async def discord_start(ctx: Ctx, db: Db, who: Who, request: Request, next: str | None = None):
    """Same shape as GitHub. The Discord identity is the one the support bot keys tickets on, so a person
    who asked in Discord and then signs in here finds the thread under /my."""
    if not ctx.settings.discord_sign_in:
        raise HTTPException(503, "Discord sign-in is not configured")
    _limit(request)
    state = secrets.token_urlsafe(24)
    db.add(
        Challenge(
            id=state,
            kind="oauth-discord",
            user_id=None,
            challenge=b"",
            expires_at=auth.now() + auth.CHALLENGE_TTL,
            detail={"next": _safe_next(ctx, next), "link_to": who.reporter.id if who.reporter else None},
        )
    )
    await db.commit()
    q = urlencode(
        {
            "client_id": ctx.settings.discord_app_id,
            "redirect_uri": _discord_callback_url(ctx),
            "response_type": "code",
            "scope": "identify email",
            "state": state,
            "prompt": "none",
        }
    )
    return RedirectResponse(f"https://discord.com/oauth2/authorize?{q}", status_code=302)


@router.get("/auth/discord/callback")
async def discord_callback(
    ctx: Ctx, db: Db, request: Request, code: str = "", state: str = "", error: str = ""
):
    ch = (await db.execute(select(Challenge).where(Challenge.id == state))).scalar_one_or_none()
    if ch is None or ch.kind != "oauth-discord" or ch.expires_at < auth.now():
        raise HTTPException(400, "sign-in expired or state mismatch; start again")
    await db.execute(delete(Challenge).where(Challenge.id == state))
    if error or not code:
        raise HTTPException(400, f"Discord did not sign you in: {error or 'no code'}")
    async with httpx.AsyncClient(timeout=15) as client:
        tok = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": ctx.settings.discord_app_id,
                "client_secret": ctx.settings.discord_oauth_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": _discord_callback_url(ctx),
            },
            headers={"Accept": "application/json"},
        )
        access = (tok.json() if tok.status_code == 200 else {}).get("access_token")
        if not access:
            raise HTTPException(400, "Discord did not return a token; start again")
        h = {"Authorization": f"Bearer {access}"}
        user = (await client.get("https://discord.com/api/users/@me", headers=h)).json()
    if not isinstance(user, dict) or "id" not in user:
        raise HTTPException(400, "Discord returned no user; start again")
    link_to = await rsvc.get(db, ch.detail.get("link_to")) if ch.detail.get("link_to") else None
    r = await channels.from_platform(
        ctx,
        db,
        "discord",
        str(user["id"]),
        name=user.get("global_name") or user.get("username") or "",
        handle=user.get("username") or "",
        email=(user.get("email") or "") if user.get("verified") else "",
        link_to=link_to,
    )
    resp = RedirectResponse(ch.detail.get("next") or "/my", status_code=302)
    await _sign_in(ctx, db, request, resp, r, "discord")
    return resp


# ---- email link ---------------------------------------------------------------------------------------


class EmailIn(BaseModel):
    email: str
    next: str | None = None


@router.post("/auth/email")
async def email_start(ctx: Ctx, db: Db, who: Who, request: Request, body: EmailIn):
    """Send a one-time link. The response is the same whether or not the address is known."""
    _limit(request)
    email = rsvc.clean_email(body.email)
    existing = await rsvc.by_email(db, email)
    link_to = who.reporter.id if who.reporter else (existing.id if existing else None)
    raw = await auth.create_reporter_link(db, email, link_to, _safe_next(ctx, body.next))
    await db.commit()
    host = ctx.settings.hosts["bounty"]
    url = f"{ctx.settings.scheme}://{host}/v1/reporter/auth/email/{raw}"
    sent = await auth.send_mail(
        ctx.settings,
        email,
        f"Sign in to {ctx.config.copy_public.get('bounty_name', 'the XE desk')}",
        f"Open this link within fifteen minutes to sign in:\n\n{url}\n\n"
        "If you did not ask for it, ignore it.",
    )
    note = None if sent else "mail is not configured on this desk; ask the team"
    return {"ok": True, "sent": sent, "note": note}


@router.get("/auth/email/{token}")
async def email_finish(ctx: Ctx, db: Db, request: Request, token: str):
    _limit(request)
    link = await auth.consume_reporter_link(db, token)
    if link is None:
        raise HTTPException(400, "that link has expired or was already used; ask for a new one")
    link_to = await rsvc.get(db, link.reporter_id) if link.reporter_id else None
    r = await rsvc.from_email(ctx, db, link.email, link_to=link_to)
    resp = RedirectResponse(link.next_path or "/my", status_code=302)
    await _sign_in(ctx, db, request, resp, r, "email")
    return resp


# ---- XE key -----------------------------------------------------------------------------------------


@router.post("/auth/xe")
async def xe_login(ctx: Ctx, db: Db, who: Who, request: Request, response: Response, req: auth.SignedRequest):
    """A signed request under xe/desk/login/v1. Payload: {"host": <this host>}; anything else is ignored.
    The address the key derives to is the identity. Signed in already: adds the address to that account."""
    _limit(request)
    v = await auth.verify_signed(db, req, DOMAIN_LOGIN)
    r = await rsvc.from_xe(ctx, db, v, link_to=who.reporter)
    return await _sign_in(ctx, db, request, response, r, "xe")


@router.post("/payout")
async def bind_payout(ctx: Ctx, db: Db, who: Who, request: Request, req: auth.SignedRequest):
    """A signed request under xe/desk/payout/v1 with payload {"address": A}, signed by A's key."""
    r = _reporter(who, request)
    v = await auth.verify_signed(db, req, DOMAIN_PAYOUT)
    out = await rsvc.bind_payout(ctx, db, r, v)
    await db.commit()
    return out


# ---- session ----------------------------------------------------------------------------------------


@router.post("/logout")
async def logout(ctx: Ctx, db: Db, who: Who, request: Request, response: Response):
    if who.reporter_session is not None:
        await auth.end_reporter_session(db, request)
        await db.commit()
    auth.clear_session_cookie(response, ctx.settings, name=auth.REPORTER_COOKIE)
    return {"ok": True}


@router.get("/me")
async def me(ctx: Ctx, db: Db, who: Who):
    if who.reporter is None:
        return {"reporter": None}
    mine = await rsvc.my_tickets(db, who.reporter)
    return {
        "reporter": rsvc.to_dict(who.reporter),
        "csrf": who.csrf,
        "tickets": [tsvc.to_dict(ctx, t, who.principal) for t in mine],
        "github_sign_in": bool(ctx.settings.github_oauth_client_id),
        "discord_sign_in": ctx.settings.discord_sign_in,
        "mail": bool(ctx.settings.smtp_host),
    }


# ---- filing -----------------------------------------------------------------------------------------


@router.post("/tickets")
async def file_ticket(
    ctx: Ctx,
    db: Db,
    who: Who,
    request: Request,
    title: str = Form(...),
    body: str = Form(...),
    kind: str = Form("bounty"),
    area: str | None = Form(None),
    claimed_tier: str | None = Form(None),
    private: bool = Form(False),
    files: list[UploadFile] = File(default=[]),
):
    """Multipart, so attachments ride along. Returns the ticket id and URL; the page redirects there."""
    r = _reporter(who, request)
    _limit(request, _filings, FILE_LIMIT, FILE_WINDOW, "reports")
    f = rsvc.Filing(
        kind=kind,
        title=title,
        body=body,
        area=area or None,
        claimed_tier=claimed_tier or None,
        private=private,
        files=[u for u in files if u.filename],
    )
    t = await rsvc.file_ticket(ctx, db, r, f)
    await db.commit()
    return {"ticket": t.id, "url": tsvc.ticket_url(ctx, t), "visibility": t.visibility}


class TextIn(BaseModel):
    body: str = ""


@router.post("/tickets/{tid}/messages")
async def reporter_reply(ctx: Ctx, db: Db, who: Who, request: Request, tid: str, body: TextIn):
    r = _reporter(who, request)
    t = await tsvc.get_for(db, who.principal, tid)
    m = await rsvc.reply(ctx, db, r, t, body.body)
    await db.commit()
    return {"ok": True, "message": m.id if m else None, "status": t.status}


@router.post("/tickets/{tid}/withdraw")
async def reporter_withdraw(ctx: Ctx, db: Db, who: Who, request: Request, tid: str, body: TextIn):
    r = _reporter(who, request)
    t = await tsvc.get_for(db, who.principal, tid)
    await rsvc.withdraw(ctx, db, r, t, body.body)
    await db.commit()
    return {"ok": True, "status": t.status, "closed_reason": t.closed_reason}


@router.get("/tickets/{tid}/attachments")
async def list_attachments(ctx: Ctx, db: Db, who: Who, tid: str):
    t = await tsvc.get_for(db, who.principal, tid)
    if not (who.principal.is_team or rsvc.owns(who.reporter, t)):
        raise HTTPException(403, "attachments open for the reporter and the team only")
    rows = await rsvc.attachments_for(db, t)
    return {
        "attachments": [
            {"n": a.n, "filename": a.filename, "size": a.size, "sha256": a.sha256, "sealed": a.sealed}
            for a in rows
        ]
    }


@router.get("/tickets/{tid}/attachments/{n}")
async def get_attachment(ctx: Ctx, db: Db, who: Who, tid: str, n: int):
    t = await tsvc.get_for(db, who.principal, tid)
    if not (who.principal.is_team or rsvc.owns(who.reporter, t)):
        raise HTTPException(403, "attachments open for the reporter and the team only")
    a, data = await rsvc.open_attachment(ctx, db, who.principal, t, n)
    await db.commit()
    safe = a.filename.replace('"', "")
    return Response(
        content=data,
        media_type="application/octet-stream",  # never rendered inline, whatever it claims to be
        headers={
            "Content-Disposition": f'attachment; filename="{safe}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "X-Desk-SHA256": a.sha256,
        },
    )

