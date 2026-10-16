"""Explicit v3 connection boundary with transaction-local tenant and service roles."""

import os
import uuid
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def mode():
    value = os.getenv("SKYVIEW_DATA_MODE", "legacy")
    if value not in ("legacy", "v3_demo", "v3_live"):
        raise RuntimeError("Invalid SKYVIEW_DATA_MODE")
    return value


def enabled():
    return mode() != "legacy"


@lru_cache(maxsize=4)
def _engine(url):
    parsed = make_url(url)
    expected = {"v3_demo": "skyview_v3_demo", "v3_live": "skyview_v3_live"}
    if parsed.database not in (expected.get(mode()), "skyview_v3_test"):
        raise RuntimeError("V3_DATABASE_URL must target the selected v3 database")
    if parsed.get_backend_name() != "postgresql":
        raise RuntimeError("V3 requires PostgreSQL; no silent SQLite fallback")
    return create_engine(
        url,
        pool_size=8,
        max_overflow=12,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"connect_timeout": 5},
        echo=False,
    )


def engine():
    if not enabled():
        raise RuntimeError("V3 is not enabled")
    url = os.getenv("V3_DATABASE_URL")
    if not url:
        raise RuntimeError("V3_DATABASE_URL is required in v3 mode")
    # Check the lane even on cache hits; a previous pool must never bypass it.
    parsed = make_url(url)
    expected = {"v3_demo": "skyview_v3_demo", "v3_live": "skyview_v3_live"}
    if parsed.database not in (expected.get(mode()), "skyview_v3_test"):
        raise RuntimeError("V3_DATABASE_URL must target the selected v3 database")
    return _engine(url)


@contextmanager
def connection(farmer_id=None, write=False, ingest=False):
    """Owner comes from a verified server session, never query/body phone or farmer ID.

    ingest is for bounded trusted workers only; browser endpoints never expose SQL or
    this role. All role/owner state is SET LOCAL and disappears at commit/rollback.
    """
    owner = str(uuid.UUID(str(farmer_id))) if farmer_id is not None else ""
    role = "sv3_ingest" if ingest else "sv3_writer" if write else "sv3_app"
    with engine().begin() as db:
        db.execute(text(f"SET LOCAL ROLE {role}"))  # constant allowlist above
        db.execute(text("SELECT set_config('search_path','sv3,pg_catalog',true)"))
        db.execute(
            text("SELECT set_config('app.farmer_id',:owner,true)"), {"owner": owner}
        )
        db.execute(text("SET LOCAL statement_timeout = '12s'"))
        db.execute(text("SET LOCAL lock_timeout = '3s'"))
        yield db


def health():
    with connection() as db:
        return db.execute(
            text("SELECT to_regclass('sv3.farmers') IS NOT NULL")
        ).scalar()


def dispose():
    _engine.cache_clear()
