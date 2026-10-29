"""Telling the reporter. A private report's thread is only visible on the desk, so without this a reporter
who signed in with a key would have to come back and look. One rule: when the team replies and the
account has a confirmed email, mail it. Chat-sourced tickets are told in their thread by the bot instead.
Mail never blocks or fails the reply; a miss is logged."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth
from ..context import Context
from ..models import Reporter, Ticket
from .tickets import ticket_url

# the chat sources; the bot tells those threads itself (channels.CHANNELS, not imported: thread imports us)
CHAT = ("discord", "telegram")

log = logging.getLogger("desk.notify")


async def reply_to_reporter(ctx: Context, db: AsyncSession, t: Ticket, author: str, body: str) -> bool:
    """Mail the reporter about a team reply on `t`. Private tickets get the fact and the link, not the
    text; public ones get the text as well. Returns whether a mail went out."""
    if t.source in CHAT or not t.reporter_id or not ctx.settings.smtp_host:
        return False
    r = (await db.execute(select(Reporter).where(Reporter.id == t.reporter_id))).scalar_one_or_none()
    if r is None or not r.email:
        return False
    url = ticket_url(ctx, t)
    noun = "question" if t.kind == "support" else "report"
    subject = f"{t.id}: {author} replied"
    if t.visibility == "public":
        text = f"{author} replied to your {noun} {t.id}, {t.title}:\n\n{body}\n\nFollow it at {url}"
    else:
        text = (
            f"{author} replied to your private {noun} {t.id}. The thread is only readable on the desk, "
            f"signed in as you:\n\n{url}"
        )
    sent = await auth.send_mail(ctx.settings, r.email, subject, text)
    if not sent:
        log.warning("reply on %s not mailed to reporter %s", t.id, r.id)
    return sent
