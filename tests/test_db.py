"""Against a real Postgres: the log chain, the ticket flow, proposals, the outbox, and the triage import
of the actual doc. Skipped unless DESK_TEST_DATABASE_URL is set, e.g.
DESK_TEST_DATABASE_URL=postgresql+asyncpg://desk:pw@db:5432/desk_test (a scratch database; it is wiped).

Run on the VPS:  docker compose exec -e DESK_TEST_DATABASE_URL=... app pytest tests/test_db.py -q
"""

import hashlib
import os
import time
from collections import Counter
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from desk import auth, authz
from desk.auth import SignedRequest, signing_target, verify_signed
from desk.canonical import DOMAIN_LOGIN, DOMAIN_PAYOUT
from desk.config import load_config
from desk.context import Context, NodeIdentity
from desk.db import Base
from desk.log import EventLog
from desk.models import AgentToken, Note, Proposal, Reply, Ticket, User
from desk.services import proposals as psvc
from desk.services import reporters as rsvc
from desk.services import thread, triage, users
from desk.services import tickets as tsvc
from desk.services.tickets import utcnow
from desk.settings import Settings
from desk.signer import Signer
from desk.vault import Vault
from xe.keys import KeyPair

URL = os.environ.get("DESK_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="DESK_TEST_DATABASE_URL not set")
ROOT = Path(__file__).resolve().parents[1]


class _NoChain:
    async def node(self):
        return {"network_id": "testnet-0005", "id": "x", "version": "t"}

    async def aclose(self):
        pass


@pytest.fixture
async def db():
    eng = create_async_engine(URL)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("INSERT INTO log_head (id, index, hash) VALUES (1, -1, repeat('0', 64))"))
        await conn.execute(text("INSERT INTO id_counters (kind, next) VALUES ('bounty', 1), ('support', 1)"))
    sm = async_sessionmaker(eng, expire_on_commit=False)
    async with sm() as s:
        yield s
    await eng.dispose()


@pytest.fixture
def ctx():
    signer = Signer(
        {"log": KeyPair.generate(), "vault": KeyPair.generate()},
        {"log": {"event.sign"}, "vault": {"vault.seal", "vault.open"}},
    )
    settings = Settings(
        DESK_BOUNTY_HOST="bounty.test",
        DESK_SUPPORT_HOST="support.test",
        PUBLIC_BASE_URL="https://bounty.test",
    )
    c = Context(
        settings=settings,
        config=load_config(ROOT / "config"),
        signer=signer,
        vault=Vault(signer),
        chain=_NoChain(),
        events=EventLog(signer),
        node=NodeIdentity(network_id="testnet-0005"),
    )
    return c


async def _team(ctx, db, roles=("reviewer", "tier", "treasurer", "admin")):
    u = await users.create_user(ctx, db, "test", "cto@xe.network", "CTO", list(roles))
    return authz.Principal(kind="user", user=u, roles=set(roles))


async def _agent(ctx, db, owner: User, scopes=("read:public", "write:notes", "write:proposals")):
    tok, _raw = await users.issue(
        ctx, db, authz.Principal(kind="user", user=owner, roles={"admin"}), owner, "m", "t", list(scopes), 30
    )
    return authz.Principal(kind="token", token=tok, scopes=set(scopes))


# ---- log --------------------------------------------------------------------------------------------


async def test_log_chain_verifies_and_detects_tamper(ctx, db):
    for i in range(4):
        await ctx.events.append(db, "test", "desk", {"i": i}, public=(i % 2 == 0))
    await db.commit()
    res = await EventLog.verify(db)
    assert res["ok"] and res["count"] == 4
    assert len(await EventLog.since(db, -1, public_only=True)) == 2
    await db.execute(text("UPDATE events SET payload = '{\"i\": 9}'::jsonb WHERE index = 2"))
    await db.commit()
    assert "hash mismatch at 2" in (await EventLog.verify(db))["first_error"]


# ---- tickets ----------------------------------------------------------------------------------------


async def test_ticket_lifecycle(ctx, db):
    p = await _team(ctx, db)
    t = await tsvc.create(
        ctx, db, p.actor, tsvc.NewTicket(kind="bounty", title="A crash", body="steps", source="web")
    )
    assert t.id == "XE-0001"
    t2 = await tsvc.create(ctx, db, p.actor, tsvc.NewTicket(kind="support", title="Faucet?", source="web"))
    assert t2.id == "XS-0001"
    await tsvc.set_facts(
        ctx,
        db,
        p,
        t,
        {"verdict": "valid", "assessed_tier": "high", "mainnet_gate": "before", "area": "node-api"},
    )
    with pytest.raises(HTTPException):
        await tsvc.set_facts(ctx, db, p, t, {"assessed_tier": "enormous"})
    with pytest.raises(HTTPException):
        await tsvc.set_status(ctx, db, p, t, "paid")
    await tsvc.set_status(ctx, db, p, t, "triaging")
    await tsvc.set_status(ctx, db, p, t, "accepted")
    await tsvc.set_status(ctx, db, p, t, "patched")
    assert t.status_changed_at is not None
    # outbox: patched and never told
    assert [x.id for x in await tsvc.outbox(db, ctx.config, p)] == ["XE-0001"]
    r = await thread.add_reply(ctx, db, p, t, "Fixed in #27, thank you.")
    assert r.mirror == "none" and t.told_at is not None
    assert await tsvc.outbox(db, ctx.config, p) == []
    # award needs the treasurer and approval before awarded
    with pytest.raises(HTTPException):
        await tsvc.set_status(ctx, db, p, t, "awarded")
    await tsvc.set_award(ctx, db, p, t, 5_000_000_000, approve=True)
    await tsvc.set_status(ctx, db, p, t, "awarded")
    await db.commit()
    board = await tsvc.leaderboard(db)
    assert board == []  # no reporter attached
    kinds = Counter(e.kind for e in await EventLog.page(db, 0, 100, ref=t.id))
    assert (
        kinds["ticket.status"] == 4
        and kinds["ticket.facts"] == 1
        and kinds["reply.sent"] == 1
        and kinds["ticket.award"] == 1
    )


async def test_private_ticket_is_sealed_and_hidden(ctx, db):
    p = await _team(ctx, db)
    t = await tsvc.create(
        ctx,
        db,
        p.actor,
        tsvc.NewTicket(
            kind="bounty",
            title="secret",
            body="the exploit",
            visibility="private",
            source="email",
            source_ref="E9",
        ),
    )
    assert t.body == "" and t.body_sealed and tsvc.body_for(ctx, t) == "the exploit"
    row = (await db.execute(text("SELECT body, body_sealed FROM tickets WHERE id = :id"), {"id": t.id})).one()
    assert row[0] == "" and b"exploit" not in bytes(row[1])
    assert await tsvc.list_tickets(db, ctx.config, authz.ANON, tsvc.Filters(status="all")) == []
    with pytest.raises(HTTPException) as e:
        await tsvc.get_for(db, authz.ANON, t.id)
    assert e.value.status_code == 404
    evs = await EventLog.page(db, 0, 10, ref=t.id, public_only=True)
    assert evs == []


async def test_severity_sort(ctx, db):
    p = await _team(ctx, db)
    a = await tsvc.create(ctx, db, p.actor, tsvc.NewTicket(kind="bounty", title="minor", source="web"))
    b = await tsvc.create(ctx, db, p.actor, tsvc.NewTicket(kind="bounty", title="severe", source="web"))
    c = await tsvc.create(
        ctx,
        db,
        p.actor,
        tsvc.NewTicket(kind="bounty", title="claimed high", source="web", claimed_tier="high"),
    )
    await tsvc.set_facts(ctx, db, p, a, {"assessed_tier": "minor"})
    await tsvc.set_facts(ctx, db, p, b, {"assessed_tier": "severe"})
    rows = await tsvc.list_tickets(db, ctx.config, p, tsvc.Filters())
    assert [r.id for r in rows] == [b.id, a.id, c.id]


# ---- proposals --------------------------------------------------------------------------------------


async def test_agent_proposes_human_adopts(ctx, db):
    p = await _team(ctx, db, roles=("reviewer",))
    agent = await _agent(ctx, db, p.user)
    t = await tsvc.create(ctx, db, p.actor, tsvc.NewTicket(kind="bounty", title="x", source="web"))
    with pytest.raises(HTTPException):
        await psvc.propose(ctx, db, p, t, "verdict", "valid", "people set facts directly")
    pr1 = await psvc.propose(ctx, db, agent, t, "verdict", "valid", "reproduced")
    pr2 = await psvc.propose(ctx, db, agent, t, "assessed_tier", "high", "targeted DoS")
    pr3 = await psvc.propose(ctx, db, agent, t, "reply_draft", "Thanks, reproduced.", "")
    out = await psvc.decide(ctx, db, p, pr1, True)
    assert out["diff"]["verdict"]["to"] == "valid" and t.verdict == "valid"
    with pytest.raises(HTTPException) as e:
        await psvc.decide(ctx, db, p, pr2, True)  # reviewer lacks the tier role
    assert e.value.status_code == 403 and pr2.state == "pending"
    out = await psvc.decide(ctx, db, p, pr3, True)
    assert out["reply_draft"] == "Thanks, reproduced." and t.status == "new"
    assert (await db.execute(select(Reply))).scalars().all() == []
    with pytest.raises(HTTPException):
        await psvc.decide(ctx, db, agent, pr2, False)
    # a repeat proposal supersedes the pending one
    pr4 = await psvc.propose(ctx, db, agent, t, "assessed_tier", "medium", "second look")
    await db.refresh(pr2)
    assert pr2.state == "superseded" and pr4.state == "pending"
    note = await thread.add_note(ctx, db, agent, t, "internal")
    assert note.author == f"token:{agent.token.id}"
    pub = await EventLog.page(db, 0, 100, ref=t.id, public_only=True)
    assert not any("Thanks, reproduced" in str(e.payload) for e in pub), "drafts never land in the public log"


# ---- triage import ----------------------------------------------------------------------------------


async def test_triage_import_of_the_real_doc(ctx, db, triage_text):
    await _team(ctx, db)
    rows = triage.parse_triage(triage_text)
    stats = await triage.import_rows(ctx, db, rows, email_bodies={"E1": "e1", "E2": "e2", "E3": "e3"})
    await db.commit()
    assert stats["created"] == 90 and stats["notes"] >= 70
    tickets = {t.source_ref: t for t in (await db.execute(select(Ticket))).scalars().all()}
    assert len(tickets) == 90
    assert tickets["15"].status == "patched" and tickets["15"].internal_ref == "#1028"
    assert tickets["70"].status == "fixing"
    assert (
        tickets["89"].status == "closed"
        and tickets["89"].duplicate_of == tickets["15"].id
        and tickets["89"].internal_ref == "#1028"
    )
    assert tickets["E1"].visibility == "private" and tickets["E1"].duplicate_of == tickets["14"].id
    assert tickets["E1"].body == "" and tsvc.body_for(ctx, tickets["E1"]) == "e1"
    assert tickets["61"].duplicate_of == tickets["E1"].id
    assert (
        tickets["99"].kind == "support"
        and tickets["99"].status == "closed"
        and tickets["99"].internal_ref == "faucet#10"
    )
    assert tickets["8"].assessed_tier == "severe" and tickets["8"].claimed_tier is None  # "mixed" bundle
    assert tickets["21"].mainnet_gate == "decide" and tickets["21"].status == "accepted"
    gates = Counter(t.mainnet_gate for t in tickets.values())
    assert gates["before"] == 35 and gates["later"] == 29 and gates["decide"] == 1  # as the rows say
    prs = {(p.repo, p.ref) for p in await thread.patches_for(db, tickets["15"])}
    assert prs == {("xeprotocol/xe", "27"), ("xeprotocol/xe", "111"), ("xeprotocol/xe", "1029")}
    notes = (await db.execute(select(Note).where(Note.ticket_id == tickets["96"].id))).scalars().all()
    assert len(notes) == 1 and "First reading" in notes[0].body and notes[0].author.startswith("token:")
    tok = (await db.execute(select(AgentToken))).scalars().one()
    assert tok.revoked_at is not None and tok.scopes == []
    # the outbox holds what was fixed and never told
    outbox = await tsvc.outbox(db, ctx.config, authz.SYSTEM)
    assert tickets["15"].id in {t.id for t in outbox}
    # re-running changes nothing
    again = await triage.import_rows(ctx, db, rows, email_bodies={})
    await db.commit()
    assert again["created"] == 0 and again["updated"] == 0 and again["notes"] == 0 and again["patches"] == 0
    assert (await EventLog.verify(db))["ok"]
    md = await triage.export_markdown(ctx, db, authz.SYSTEM)
    assert "XE-" in md and "`#1028`" in md and md.count("\n| ") >= 90
    public_md = await triage.export_markdown(ctx, db, authz.ANON)
    assert tickets["E1"].title in md and tickets["E1"].title not in public_md
    assert public_md.count("\n| ") == md.count("\n| ") - 3
    pending = (await db.execute(select(Proposal))).scalars().all()
    assert pending == [], "the import writes facts, not proposals"


# ---- reporters -------------------------------------------------------------------------------------


class _Upload:
    """Just enough of starlette's UploadFile for the service."""

    def __init__(self, name: str, data: bytes, content_type: str = "text/plain"):
        self.filename, self._data, self.content_type = name, data, content_type

    async def read(self, n: int = -1) -> bytes:
        d, self._data = self._data[:n] if n >= 0 else self._data, b""
        return d


def _signed(kp: KeyPair, domain: bytes, payload: dict) -> SignedRequest:
    ts = time.time_ns()
    sig = kp.sign_hex(signing_target(domain, payload, ts))
    return SignedRequest(payload=payload, timestamp=ts, pub_key=kp.pub_key_hex, signature=sig)


async def test_reporter_files_private_report_with_sealed_attachment(ctx, db, tmp_path):
    ctx.settings.blob_dir = tmp_path
    r = await rsvc.from_email(ctx, db, "alice@example.org", link_to=None)
    me = authz.Principal(kind="reporter", reporter_id=r.id)
    f = rsvc.Filing(
        kind="bounty",
        title="Escrow release double-counts",
        body="Steps: open an escrow, release twice within one block. Expected: one release. Got: two.",
        area="consensus",
        claimed_tier="high",
        private=True,
        files=[_Upload("poc.txt", b"the exploit bytes " * 10)],
    )
    t = await rsvc.file_ticket(ctx, db, r, f)
    await db.commit()
    assert t.visibility == "private" and t.reporter_id == r.id and t.claimed_tier == "high"
    assert tsvc.body_for(ctx, t).startswith("Steps")
    atts = await rsvc.attachments_for(db, t)
    assert len(atts) == 1 and atts[0].sealed
    on_disk = (tmp_path / atts[0].blob_path).read_bytes()
    assert b"exploit" not in on_disk
    a, data = await rsvc.open_attachment(ctx, db, me, t, 1)
    assert data.startswith(b"the exploit") and a.sha256 == hashlib.sha256(data).hexdigest()
    # the reporter sees their own private ticket; anonymous and another reporter do not
    assert (await tsvc.get_for(db, me, t.id)).id == t.id
    other = authz.Principal(kind="reporter", reporter_id=r.id + 1)
    for p in (authz.ANON, other):
        with pytest.raises(HTTPException) as e:
            await tsvc.get_for(db, p, t.id)
        assert e.value.status_code == 404
    assert not rsvc.owns(None, t)


async def test_critical_claim_forces_private(ctx, db):
    r = await rsvc.from_email(ctx, db, "bob@example.org", link_to=None)
    f = rsvc.Filing(
        kind="bounty",
        title="Unauthorized mint via vault",
        body="A long enough description of how the mint can be triggered without authorisation here.",
        claimed_tier="critical",
        private=False,
    )
    t = await rsvc.file_ticket(ctx, db, r, f)
    assert t.visibility == "private"


async def test_reporter_withdraws_and_replies(ctx, db):
    r = await rsvc.from_email(ctx, db, "carol@example.org", link_to=None)
    team = await _team(ctx, db)
    body = "What I did, what happened, what I expected; enough words to pass the body check."
    f = rsvc.Filing(kind="bounty", title="Explorer shows wrong tip", body=body)
    t = await rsvc.file_ticket(ctx, db, r, f)
    await tsvc.set_status(ctx, db, team, t, "triaging")
    await tsvc.set_status(ctx, db, team, t, "needs-info")
    m = await rsvc.reply(ctx, db, r, t, "Here is the version: 0.5.1")
    assert m is not None and t.status == "triaging"
    await rsvc.withdraw(ctx, db, r, t, "my mistake")
    assert t.status == "closed" and t.closed_reason == "withdrawn"
    with pytest.raises(HTTPException) as e:
        await rsvc.withdraw(ctx, db, r, t)
    assert e.value.status_code == 409
    stranger = await rsvc.from_email(ctx, db, "dave@example.org", link_to=None)
    with pytest.raises(HTTPException) as e:
        await rsvc.reply(ctx, db, stranger, t, "mine now")
    assert e.value.status_code == 403


async def test_payout_binding_needs_matching_key(ctx, db):
    r = await rsvc.from_email(ctx, db, "erin@example.org", link_to=None)
    body = "A public report with enough body to be accepted by the filing checks, no secrets inside."
    f = rsvc.Filing(kind="bounty", title="Typo on the faucet page", body=body)
    t = await rsvc.file_ticket(ctx, db, r, f)
    kp, wrong = KeyPair.generate(), KeyPair.generate()
    v = await verify_signed(db, _signed(kp, DOMAIN_PAYOUT, {"address": wrong.address}), DOMAIN_PAYOUT)
    with pytest.raises(HTTPException) as e:
        await rsvc.bind_payout(ctx, db, r, v)
    assert e.value.status_code == 400
    v = await verify_signed(db, _signed(kp, DOMAIN_PAYOUT, {"address": kp.address}), DOMAIN_PAYOUT)
    out = await rsvc.bind_payout(ctx, db, r, v)
    assert out == {"address": kp.address, "tickets_updated": 1}
    assert r.xe_address == kp.address and t.payout_address == kp.address
    # the payout export lists approved awards with the bound address
    await tsvc.set_status(ctx, db, await _team(ctx, db), t, "triaging")
    t.award_xe, t.award_approved_at = 5_000_000, utcnow()
    await db.flush()
    rows = await rsvc.payout_rows(db)
    assert rows and rows[0][0] == t.id and rows[0][3] == 5 and rows[0][-1] == kp.address


async def test_xe_login_and_identity_merge(ctx, db):
    kp = KeyPair.generate()
    v = await verify_signed(db, _signed(kp, DOMAIN_LOGIN, {"host": "bounty.test"}), DOMAIN_LOGIN)
    a = await rsvc.from_xe(ctx, db, v, link_to=None)
    assert kp.address in a.xe_login_addresses
    # an email account exists separately, with a ticket; linking email onto the key account merges them
    b = await rsvc.from_email(ctx, db, "frank@example.org", link_to=None)
    body = "Filed under the email identity before the two accounts were joined together by the reporter."
    f = rsvc.Filing(kind="support", title="Which port does a node use", body=body)
    t = await rsvc.file_ticket(ctx, db, b, f)
    merged = await rsvc.from_email(ctx, db, "frank@example.org", link_to=a)
    assert merged.id == a.id and merged.email == "frank@example.org"
    await db.refresh(t)
    assert t.reporter_id == a.id
    assert (await rsvc.get(db, b.id)).email == ""  # emptied, kept so old log entries still resolve
    # link tokens: one use, then gone
    raw = await auth.create_reporter_link(db, "frank@example.org", a.id, "/my")
    link = await auth.consume_reporter_link(db, raw)
    assert link is not None and link.reporter_id == a.id and link.next_path == "/my"
    assert await auth.consume_reporter_link(db, raw) is None
