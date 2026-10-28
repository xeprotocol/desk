from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import Auth, resolve
from ..context import Context, get_context
from ..db import get_db

Ctx = Annotated[Context, Depends(get_context)]
Db = Annotated[AsyncSession, Depends(get_db)]


async def current(db: Db, request: Request) -> Auth:
    return await resolve(db, request)


Who = Annotated[Auth, Depends(current)]
