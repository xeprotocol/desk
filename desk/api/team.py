"""Team-only JSON, called from the pages' small scripts with the session cookie and the CSRF header.
Every route refuses tokens through the authorisation layer. Mutations commit here."""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..auth import check_csrf
from ..authz import can, require, require_field
from ..services import proposals as psvc
from ..services import reporters as rsvc
from ..services import thread, users
from ..services import tickets as tsvc
from .deps import Ctx, Db, Who

router = APIRouter(prefix="/v1/team", tags=["team"])


def _team(who: Who, request: Request) -> None:
    p = who.principal
    if p.kind != "user" or not p.roles:
        raise HTTPException(401 if p.kind == "anon" else 403, "team sign-in required")
    if who.session is not None and request.method not in ("GET", "HEAD"):
        check_csrf(request, who.session)


class FactsIn(BaseModel):
    changes: dict[str, Any]
    reason: str = Field(default="", max_length=500)


class StatusIn(BaseModel):
    status: str
    closed_reason: str | None = None
    reason: str = Field(default="", max_length=500)


class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)


class DecideIn(BaseModel):
    reason: str = Field(default="", max_length=500)


class AwardIn(BaseModel):
    award_xe: int | None = None
    approve: bool = False


class NewTicketIn(BaseModel):
    kind: str = "bounty"
    title: str = Field(min_length=3, max_length=512)
    body: str = ""
    visibility: str = "public"
    source: str = "web"
    area: str | None = None
    claimed_tier: str | None = None


# ---- tickets ----------------------------------------------------------------------------------------


@router.post("/tickets", status_code=201)
async def create_ticket(ctx: Ctx, db: Db, who: Who, request: Request, body: NewTicketIn):
    _team(who, request)
    spec = tsvc.NewTicket(
        kind=body.kind,
        title=body.title,
        body=body.body,
        visibility=body.visibility,
        source=body.source,
        area=body.area,
        claimed_tier=body.claimed_tier,
    )
    t = await tsvc.create(ctx, db, who.principal.actor, spec)
    await db.commit()
    return tsvc.to_dict(ctx, t, who.principal)


@router.patch("/tickets/{tid}/facts")
async def set_facts(ctx: Ctx, db: Db, who: Who, request: Request, tid: str, body: FactsIn):
    _team(who, request)
    t = await tsvc.get_for(db, who.principal, tid)
    for k in body.changes:
        require_field(who.principal, k)
    diff = await tsvc.set_facts(ctx, db, who.principal, t, body.changes, reason=body.reason)
    await db.commit()
    return {"ticket": t.id, "changes": diff}


@router.post("/tickets/{tid}/status")
async def set_status(ctx: Ctx, db: Db, who: Who, request: Request, tid: str, body: StatusIn):
    _team(who, request)
    t = await tsvc.get_for(db, who.principal, tid)
    require_field(who.principal, "status")
    if body.status == "disclosed":
        await tsvc.disclose(ctx, db, who.principal, t)
    else:
        await tsvc.set_status(
            ctx, db, who.principal, t, body.status, closed_reason=body.closed_reason, reason=body.reason
        )
    await db.commit()
    return tsvc.to_dict(ctx, t, who.principal)


@router.post("/tickets/{tid}/kind")
async def set_kind(ctx: Ctx, db: Db, who: Who, request: Request, tid: str, kind: str):
    """Support that turns out to be a bug (or the reverse). The id and the history stay."""
    _team(who, request)
    t = await tsvc.get_for(db, who.principal, tid)
    require(who.principal, "facts", t)
    if kind not in ("bounty", "support") or kind == t.kind:
        raise HTTPException(400, "kind is bounty or support, and must change")
    old = t.kind
    t.kind = kind
    t.area = None  # areas are engineering areas on the bounty and topics on support; neither carries over
    if kind == "support" and t.status not in ("new", "triaging", "needs-info", "closed"):
        await tsvc.set_status(
            ctx, db, who.principal, t, "triaging", force=True, reason="converted to support"
        )
    await ctx.events.append(
        db,
        "ticket.kind",
        who.principal.actor,
        {"ticket": t.id, "from": old, "to": kind},
        ref=t.id,
        public=t.visibility == "public",
    )
    await db.commit()
    return tsvc.to_dict(ctx, t, who.principal)


@router.post("/tickets/{tid}/replies", status_code=201)
async def reply(ctx: Ctx, db: Db, who: Who, request: Request, tid: str, body: ReplyIn):
    _team(who, request)
    t = await tsvc.get_for(db, who.principal, tid)
    require(who.principal, "reply", t)
    r = await thread.add_reply(ctx, db, who.principal, t, body.body)
    await db.commit()
    return {"id": r.id, "ticket": t.id, "mirror": r.mirror}


@router.get("/tickets/{tid}/reply-template/{name}")
async def reply_template(ctx: Ctx, db: Db, who: Who, request: Request, tid: str, name: str):
    _team(who, request)
    t = await tsvc.get_for(db, who.principal, tid)
    if name not in ctx.config.reply_templates:
        raise HTTPException(404, "no such template")
    prs = await thread.patches_for(db, t)
    refs = (
        ", ".join(f"{p.repo}#{p.ref}" if p.kind == "pr" else f"{p.repo}@{p.ref[:10]}" for p in prs)
        or "the linked PR"
    )
    return {"name": name, "body": thread.render_template(ctx, name, t, patch_refs=refs)}


@router.post("/tickets/{tid}/award")
async def award(ctx: Ctx, db: Db, who: Who, request: Request, tid: str, body: AwardIn):
    _team(who, request)
    t = await tsvc.get_for(db, who.principal, tid)
    require(who.principal, "award", t)
    await tsvc.set_award(ctx, db, who.principal, t, body.award_xe, approve=body.approve)
    await db.commit()
    return tsvc.to_dict(ctx, t, who.principal)


# ---- proposals --------------------------------------------------------------------------------------


@router.post("/proposals/{pid}/adopt")
async def adopt(ctx: Ctx, db: Db, who: Who, request: Request, pid: int, body: DecideIn | None = None):
    _team(who, request)
    pr = await psvc.get(db, pid)
    if pr is None:
        raise HTTPException(404, "no such proposal")
    out = await psvc.decide(ctx, db, who.principal, pr, True, reason=(body.reason if body else ""))
    await db.commit()
    return out


@router.post("/proposals/{pid}/reject")
async def reject(ctx: Ctx, db: Db, who: Who, request: Request, pid: int, body: DecideIn | None = None):
    _team(who, request)
    pr = await psvc.get(db, pid)
    if pr is None:
        raise HTTPException(404, "no such proposal")
    out = await psvc.decide(ctx, db, who.principal, pr, False, reason=(body.reason if body else ""))
    await db.commit()
    return out


class BulkIn(BaseModel):
    adopt: list[int] = []
    reject: list[int] = []


@router.post("/proposals/bulk")
async def decide_bulk(ctx: Ctx, db: Db, who: Who, request: Request, body: BulkIn):
    _team(who, request)
    out = []
    for pid, yes in [(i, True) for i in body.adopt] + [(i, False) for i in body.reject]:
        pr = await psvc.get(db, pid)
        if pr is None or pr.state != "pending":
            continue
        out.append(await psvc.decide(ctx, db, who.principal, pr, yes))
    await db.commit()
    return {"decided": out}


# ---- views ------------------------------------------------------------------------------------------


@router.get("/outbox")
async def outbox(ctx: Ctx, db: Db, who: Who, request: Request):
    _team(who, request)
    rows = await tsvc.outbox(db, ctx.config, who.principal)
    return {"tickets": [tsvc.to_dict(ctx, t, who.principal) for t in rows]}


@router.get("/release")
async def release(ctx: Ctx, db: Db, who: Who, request: Request):
    _team(who, request)
    groups = await tsvc.release_view(db, ctx.config, who.principal)
    return {area: [tsvc.to_dict(ctx, t, who.principal) for t in ts] for area, ts in groups.items()}


@router.get("/payouts")
async def payouts(ctx: Ctx, db: Db, who: Who, request: Request):
    """Approved awards not yet paid, with addresses: the treasurer's list."""
    _team(who, request)
    require(who.principal, "export:payouts")
    rows = await tsvc.list_tickets(
        db, ctx.config, who.principal, tsvc.Filters(kind="bounty", status="awarded", limit=500)
    )
    return {
        "payouts": [
            {
                "ticket": t.id,
                "award_xe": t.award_xe,
                "payout_address": t.payout_address,
                "reporter_id": t.reporter_id,
                "tier": t.assessed_tier,
            }
            for t in rows
        ]
    }


# ---- tokens and users -------------------------------------------------------------------------------


class TokenIn(BaseModel):
    model_id: str = Field(min_length=1, max_length=128)
    label: str = Field(default="", max_length=128)
    scopes: list[str]
    days: int = 90
    owner_id: int | None = None


@router.get("/tokens")
async def list_tokens(db: Db, who: Who, request: Request):
    _team(who, request)
    mine = None if can(who.principal, "admin") else who.principal.user
    return {"tokens": [users.token_dict(t) for t in await users.tokens_for(db, mine)]}


@router.post("/tokens", status_code=201)
async def issue_token(ctx: Ctx, db: Db, who: Who, request: Request, body: TokenIn):
    _team(who, request)
    require(who.principal, "tokens:issue")
    owner = who.principal.user
    if body.owner_id and body.owner_id != owner.id:
        owner = await users.by_id(db, body.owner_id)
        if owner is None:
            raise HTTPException(404, "no such user")
    t, raw = await users.issue(
        ctx, db, who.principal, owner, body.model_id, body.label, body.scopes, body.days
    )
    await db.commit()
    return {**users.token_dict(t), "token": raw, "note": "shown once; store it now"}


@router.delete("/tokens/{tid}")
async def revoke_token(ctx: Ctx, db: Db, who: Who, request: Request, tid: int):
    _team(who, request)
    t = await users.token_by_id(db, tid)
    if t is None:
        raise HTTPException(404, "no such token")
    await users.revoke(ctx, db, who.principal, t)
    await db.commit()
    return {"revoked": t.id}


class UserIn(BaseModel):
    email: str
    name: str = ""
    roles: list[str] = []


@router.get("/users")
async def list_users(db: Db, who: Who, request: Request):
    _team(who, request)
    return {"users": [users.user_dict(u) for u in await users.list_users(db)]}


@router.post("/users", status_code=201)
async def add_user(ctx: Ctx, db: Db, who: Who, request: Request, body: UserIn):
    _team(who, request)
    require(who.principal, "admin")
    u = await users.create_user(ctx, db, who.principal.actor, body.email, body.name, body.roles)
    await db.commit()
    return users.user_dict(u)


class UserEditIn(BaseModel):
    roles: list[str] | None = None
    active: bool | None = None


@router.patch("/users/{uid}")
async def edit_user(ctx: Ctx, db: Db, who: Who, request: Request, uid: int, body: UserEditIn):
    _team(who, request)
    require(who.principal, "admin")
    u = await users.by_id(db, uid)
    if u is None:
        raise HTTPException(404, "no such user")
    if body.roles is not None:
        await users.set_roles(ctx, db, who.principal.actor, u, body.roles)
    if body.active is not None:
        await users.set_active(ctx, db, who.principal.actor, u, body.active)
    await db.commit()
    return users.user_dict(u)


@router.get("/payouts.csv")
async def payouts_csv(ctx: Ctx, db: Db, who: Who, request: Request):
    """Approved awards with a bound payout address, one row each, for the genesis allocation. Tickets
    with an approved award and no address are listed too, with the address blank, so nobody is missed."""
    _team(who, request)
    require(who.principal, "export:payouts")
    rows = await rsvc.payout_rows(db)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(
        ["ticket", "title", "tier", "award_xe", "approved_at", "reporter_id", "reporter", "xe_address"]
    )
    for r in rows:
        w.writerow(r)
    return Response(
        content=out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="payouts.csv"', "Cache-Control": "no-store"},
    )
