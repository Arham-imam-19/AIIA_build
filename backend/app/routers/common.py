"""Shared helpers for the read-only Phase 1 endpoints.

Two small ideas live here so the routers stay boring:

`Page` - every list endpoint returns the same envelope: a `total` (how many rows
match, regardless of paging) and an `items` list (the slice you asked for). A
table in the UI needs both to draw "showing 50 of 186".

`paginate` - runs the count and the slice from one query, so a router never
repeats the `limit`/`offset` dance.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import func, select as sa_select
from sqlmodel import Session

T = TypeVar("T")

# Sensible ceiling: enough for any table view, small enough that a stray
# ?limit=999999 cannot drag the whole database over the wire.
MAX_PAGE_SIZE = 500


class Page(BaseModel, Generic[T]):
    """One page of results, plus the total so the UI can show "50 of 186"."""

    total: int
    limit: int
    offset: int
    items: list[T]


def limit_param(default: int = 50) -> Query:
    return Query(default, ge=1, le=MAX_PAGE_SIZE, description="rows to return")


def offset_param() -> Query:
    return Query(0, ge=0, description="rows to skip, for paging")


def paginate(session: Session, statement, limit: int, offset: int) -> tuple[int, list]:
    """Return (total_matching_rows, rows_for_this_page).

    The total is computed by wrapping the same filtered query in a COUNT, so the
    two can never disagree about which rows matched.
    """
    count_statement = sa_select(func.count()).select_from(statement.subquery())
    total = session.exec(count_statement).one()
    # SQLAlchemy returns a 1-tuple for a scalar select; SQLModel unwraps some but
    # not all. Handle both so this works whichever path is taken.
    if isinstance(total, tuple):
        total = total[0]

    rows = session.exec(statement.limit(limit).offset(offset)).all()
    return int(total), list(rows)
