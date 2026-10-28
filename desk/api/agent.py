"""What an agent token can do: read what its scopes allow, write notes, propose, link patches. There is
no route here that sets a fact, sends a reply or changes a status; those are in team.py and reject
tokens in the authorisation layer."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..authz import require
from ..services import proposals as psvc
from ..services import thread
from ..services import tickets as tsvc
from .deps import Ctx, Db, Who

router = APIRouter(prefix="/v1", tags=["agent"])


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)


class ProposalIn(BaseModel):
    field: str
    value: Any
    reason: str = Field(default="", max_length=4000)


class PatchIn(BaseModel):
    repo: str = ""
    ref: str
    kind: str = "pr"
    title: str = ""
    url: str = ""
    note: str = ""


@router.get("/tickets/{tid}/notes")
async def list_notes(db: Db, who: Who, tid: str):
    t = await tsvc.get_for(db, who.principal, tid)
    require(who.principal, "read:notes", t)
    return {
        "ticket": t.id,
        "notes": [
            {
                "id": n.id,
                "author": n.author,
                "author_name": n.author_name,
                "body": n.body,
                "created_at": thread.iso(n.created_at),
            }
            for n in await thread.notes_for(db, t)
        ],
    }


@router.post("/tickets/{tid}/notes", status_code=201)
async def add_note(ctx: Ctx, db: Db, who: Who, tid: str, body: NoteIn):
    t = await tsvc.get_for(db, who.principal, tid)
    require(who.principal, "write:notes", t)
    n = await thread.add_note(ctx, db, who.principal, t, body.body)
    await db.commit()
    return {"id": n.id, "ticket": t.id, "created_at": thread.iso(n.created_at)}


@router.get("/tickets/{tid}/proposals")
async def list_proposals(db: Db, who: Who, tid: str):
    t = await tsvc.get_for(db, who.principal, tid)
    require(who.principal, "read:notes", t)
    return {"ticket": t.id, "proposals": [psvc.to_dict(pr) for pr in await psvc.pending_for(db, t)]}


@router.post("/tickets/{tid}/proposals", status_code=201)
async def propose(ctx: Ctx, db: Db, who: Who, tid: str, body: ProposalIn):
    t = await tsvc.get_for(db, who.principal, tid)
    require(who.principal, "write:proposals", t)
    pr = await psvc.propose(ctx, db, who.principal, t, body.field, body.value, body.reason)
    await db.commit()
    return psvc.to_dict(pr, who.principal.token)


@router.post("/tickets/{tid}/proposals/bulk", status_code=201)
async def propose_bulk(ctx: Ctx, db: Db, who: Who, tid: str, body: list[ProposalIn]):
    """Several fields at once, one transaction; the usual shape after reading a new ticket."""
    if len(body) > 12:
        raise HTTPException(400, "at most 12 proposals per call")
    t = await tsvc.get_for(db, who.principal, tid)
    require(who.principal, "write:proposals", t)
    out = [
        psvc.to_dict(
            await psvc.propose(ctx, db, who.principal, t, b.field, b.value, b.reason), who.principal.token
        )
        for b in body
    ]
    await db.commit()
    return {"proposals": out}


@router.post("/tickets/{tid}/patch-refs", status_code=201)
async def add_patch(ctx: Ctx, db: Db, who: Who, tid: str, body: PatchIn):
    t = await tsvc.get_for(db, who.principal, tid)
    require(who.principal, "write:patch-refs", t)
    repo, ref = body.repo, body.ref
    if not repo:
        parsed = thread.parse_patch_token(ref, ctx.config.primary_repo)
        if parsed is None:
            raise HTTPException(400, "give repo and ref, or a token like #27, dao#1, owner/repo#5")
        repo, ref = parsed
    pr = await thread.add_patch_ref(
        ctx,
        db,
        who.principal,
        t,
        repo=repo,
        ref=ref,
        kind=body.kind,
        title=body.title,
        url=body.url,
        note=body.note,
    )
    await db.commit()
    if pr is None:
        return {"ticket": t.id, "unchanged": True}
    return {"ticket": t.id, "id": pr.id, "repo": pr.repo, "ref": pr.ref, "url": pr.url}


@router.get("/me")
async def me(who: Who):
    p = who.principal
    out: dict[str, Any] = {"kind": p.kind, "actor": p.actor, "name": p.name}
    if p.token:
        out["token"] = {
            "id": p.token.id,
            "model_id": p.token.model_id,
            "label": p.token.label,
            "scopes": p.token.scopes,
            "expires_at": thread.iso(p.token.expires_at),
        }
    if p.user:
        out["user"] = {"id": p.user.id, "email": p.user.email, "roles": sorted(p.roles)}
    return out
