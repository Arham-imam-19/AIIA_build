"""Shared helpers for every model.

Two conventions hold across the whole schema:

1. **All timestamps are naive UTC.** No local times are ever stored. Keeping
   them naive means SQLite (the no-Docker fallback) and PostgreSQL behave
   identically, and there is no chance of an IST-vs-UTC mix-up in an audit
   trail that regulators may read.

2. **No ORM `Relationship()` objects.** Tables reference each other with plain
   foreign-key columns, and joins are written out explicitly in queries. This
   avoids lazy-loading errors when a model is serialised to JSON after its
   database session has closed - a common and confusing failure. The cost is a
   few more explicit joins; the benefit is that what you see is what runs.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current UTC time, without a timezone attached. See note 1 above."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
