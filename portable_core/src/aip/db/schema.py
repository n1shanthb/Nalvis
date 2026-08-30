"""Schema bootstrap — create tables if missing (no Alembic for v1 spine)."""

from __future__ import annotations

from aip.db.orm import Base
from aip.db.session import get_engine


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
