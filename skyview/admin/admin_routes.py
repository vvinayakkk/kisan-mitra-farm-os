"""Verified, explicitly scoped administration of the canonical v3 database.

Never uses farmer capability sessions, arbitrary SQL, or the normal app DB role.
Every write is a bounded, validated preview followed by an atomic audited commit.
"""

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    MetaData,
    String,
    Table,
    and_,
    cast,
    create_engine,
    func,
    inspect,
    or_,
    select,
    text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from skyview.assistant.auth import AuthenticationUnavailable, verify_identity

# Explicit product resources. Internal sessions, secrets, prompt state, provider
# configuration, consent evidence, and device commands are deliberately excluded.
GROUPS = {
    "People": [
        "farmers",
        "farms",
        "plots",
        "crop_cycles",
        "resources",
        "expenses",
        "tasks",
        "field_observations",
        "harvest_batches",
        "sale_records",
    ],
    "Knowledge & markets": [
        "crops",
        "crop_varieties",
        "units",
        "regions",
        "locations",
        "markets",
        "market_series",
        "price_observations",
        "msp_announcements",
        "crop_guides",
        "diseases",
        "scheme_versions",
    ],
    "Weather & stations": [
        "stations",
        "station_sensors",
        "weather_series",
        "weather_daily",
        "weather_forecasts",
        "soil_samples",
        "soil_indicators",
    ],
    "Exchange": ["exchange_listings", "resource_listings"],
    "Plans & services": [
        "farm_missions",
        "companion_proposals",
        "service_requests",
        "ledger_entries",
        "crop_case_notes",
    ],
    "Activity": [
        "conversations",
        "agent_runs",
        "task_events",
        "exchange_events",
        "source_health",
        "ingest_runs",
        "datasets",
    ],
}
READ_ONLY = set(GROUPS["Activity"]) | {"farm_missions", "companion_proposals"}
RESOURCES = {name: group for group, names in GROUPS.items() for name in names}
HIDDEN = {
    "auth_subject",
    "token_hash",
    "saved_otp",
    "password",
    "run_token",
    "configuration",
    "evidence_hash",
    "request_hash",
    "result",
    "before_state",
    "after_state",
    "cursor",
    "summary",
    "safe_error",
}
OWNERSHIP_FIELDS = {
    "farmer_id",
    "owner_farmer_id",
    "owner_id",
    "requester_id",
    "creator_id",
    "dataset_id",
    "provider_id",
}
IMMUTABLE = {
    "profile_key",
    "created_at",
    "updated_at",
    "row_version",
    "contact_verified_at",
}


def require_admin(response: Response, authorization: str = Header(default="")):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in with your authorized administrator account.")
    try:
        identity = verify_identity(authorization[7:], check_revoked=True)
        grants = json.loads(os.getenv("ADMIN_IDENTITIES", "{}"))
        role = (
            grants.get(identity["auth_subject"]) if isinstance(grants, dict) else None
        )
    except AuthenticationUnavailable:
        raise HTTPException(503, "Administrator sign-in is not configured.")
    except (ValueError, TypeError):
        raise HTTPException(401, "Administrator sign-in could not be verified.")
    if role not in ("viewer", "editor", "owner"):
        raise HTTPException(403, "This account does not have administrator access.")
    return {"subject": identity["auth_subject"], "role": role}


ADMIN_ACCESS = Depends(require_admin)


router = APIRouter(
    prefix="/admin", tags=["Administration"], dependencies=[Depends(require_admin)]
)


@lru_cache(maxsize=2)
def _engine(url):
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or parsed.database not in (
        "skyview_v3_live",
        "skyview_v3_demo",
        "skyview_v3_test",
    ):
        raise ValueError("Invalid administrator database")
    if parsed.host not in ("localhost", "127.0.0.1") and parsed.query.get(
        "sslmode"
    ) not in ("require", "verify-ca", "verify-full"):
        raise ValueError("Administrator database requires TLS")
    return create_engine(
        url,
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


@contextmanager
def connection():
    url = os.getenv("ADMIN_DATABASE_URL", "")
    if not url:
        raise HTTPException(503, "The administrator database is not configured.")
    try:
        with _engine(url).begin() as db:
            db.execute(text("SET LOCAL ROLE sv3_admin"))
            db.execute(text("SET LOCAL statement_timeout = '10s'"))
            db.execute(text("SET LOCAL lock_timeout = '3s'"))
            yield db
    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError):
        raise HTTPException(
            409,
            "The operation could not be completed. Check required fields, types, unique values and linked records, then refresh. No partial batch was saved.",
        )


def table_for(db, name):
    if name not in RESOURCES:
        raise HTTPException(404, "Unknown administrator resource.")
    if not inspect(db).has_table(name, schema="sv3"):
        raise HTTPException(
            503, "This resource is not installed in the current database."
        )
    return Table(name, MetaData(), schema="sv3", autoload_with=db)


def clean(value):
    if isinstance(value, dict):
        return {
            k: clean(v)
            for k, v in value.items()
            if k not in HIDDEN
            and not any(
                s in k.lower()
                for s in ("password", "secret", "token", "otp", "api_key")
            )
        }
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def digest(row):
    return hashlib.sha256(
        json.dumps(clean(dict(row)), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def record(row):
    return {**clean(dict(row)), "_version": digest(row)}


def metadata(table, role):
    return {
        "name": table.name,
        "label": table.name.replace("_", " ").title(),
        "group": RESOURCES[table.name],
        "writable": table.name not in READ_ONLY and role != "viewer",
        "deletable": table.name not in READ_ONLY and role == "owner",
        "primary_key": [c.name for c in table.primary_key],
        "columns": [
            {
                "name": c.name,
                "type": str(c.type),
                "nullable": c.nullable,
                "default": str(getattr(c.server_default, "arg", "generated"))
                if c.server_default
                else None,
                "primary_key": c.primary_key,
                "editable": not c.computed
                and not c.identity
                and c.name not in IMMUTABLE
                and not c.primary_key
                and c.name not in OWNERSHIP_FIELDS,
                "generated": bool(c.computed or c.identity),
                "references": [
                    f"{f.column.table.name}.{f.column.name}" for f in c.foreign_keys
                ],
            }
            for c in table.c
            if c.name not in HIDDEN
        ],
    }


@router.get("/me")
def me(actor=ADMIN_ACCESS):
    return {"role": actor["role"], "subject": actor["subject"], "max_batch": 100}


@router.get("/overview")
def overview(actor=ADMIN_ACCESS):
    with connection() as db:
        result = {}
        for name in ("farmers", "farms", "tasks", "exchange_listings"):
            table = table_for(db, name)
            result[name] = db.execute(
                select(func.count()).select_from(table)
            ).scalar_one()
        return {"counts": result, "checked_at": str(datetime.now(UTC))}


@router.get("/resources")
def resources(actor=ADMIN_ACCESS):
    with connection() as db:
        installed = set(inspect(db).get_table_names(schema="sv3"))
        return {
            "resources": [
                metadata(table_for(db, name), actor["role"])
                for name in RESOURCES
                if name in installed
            ]
        }


@router.get("/resources/{name}")
def browse(
    name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str = Query("", max_length=160),
    farmer_id: str = "",
    actor=ADMIN_ACCESS,
):
    with connection() as db:
        table = table_for(db, name)
        columns = [c for c in table.c if c.name not in HIDDEN]
        conditions = []
        if search:
            columns_to_search = [c for c in columns if "JSON" not in str(c.type)]
            conditions.append(
                or_(
                    *[
                        cast(c, String).ilike(
                            "%"
                            + search.replace("\\", "\\\\")
                            .replace("%", "\\%")
                            .replace("_", "\\_")
                            + "%",
                            escape="\\",
                        )
                        for c in columns_to_search
                    ]
                )
            )
        if farmer_id:
            column = (
                table.c.get("farmer_id") if name != "farmers" else table.c.get("id")
            )
            if column is None:
                raise HTTPException(422, "This resource cannot be filtered by farmer.")
            try:
                conditions.append(column == uuid.UUID(farmer_id))
            except ValueError:
                raise HTTPException(422, "Invalid farmer identifier.")
        query = select(*columns).where(*conditions)
        ordering = (
            [table.c.created_at.desc()] if "created_at" in table.c else []
        ) + list(table.primary_key)
        rows = (
            db.execute(
                query.order_by(*ordering)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
            .mappings()
            .all()
        )
        total = db.execute(
            select(func.count()).select_from(table).where(*conditions)
        ).scalar_one()
        return {
            "records": [record(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["create", "update", "delete"]
    key: dict[str, Any] = Field(default_factory=dict)
    values: dict[str, Any] = Field(default_factory=dict)
    version: str | None = None


class Batch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operations: list[Operation] = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        if len(value.strip()) < 5:
            raise ValueError("Provide a meaningful reason.")
        return value.strip()


class Commit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: str


def validate_batch(table, batch, actor):
    if actor["role"] == "viewer" or table.name in READ_ONLY:
        raise HTTPException(403, "This resource is read-only for your role.")
    if len(batch.model_dump_json()) > 512_000:
        raise HTTPException(
            413, "The batch exceeds 500 KB. Split it into smaller batches."
        )
    visible = {c.name for c in table.c} - HIDDEN
    primary = {c.name for c in table.primary_key}
    seen = set()
    if not primary:
        raise HTTPException(422, "This resource has no stable record key.")
    for op in batch.operations:
        if op.action == "delete" and actor["role"] != "owner":
            raise HTTPException(403, "Only owners can delete records.")
        if op.action == "create":
            if op.key or op.version:
                raise HTTPException(
                    422, "New records must not have an existing key or version."
                )
            # Database-generated identifiers and timestamps cannot be supplied.
            blocked = IMMUTABLE | {
                c.name for c in table.primary_key if c.server_default
            }
        else:
            if (
                set(op.key) != primary
                or any(v is None for v in op.key.values())
                or not op.version
            ):
                raise HTTPException(
                    422,
                    "Supply the complete primary key and the current record version.",
                )
            marker = json.dumps(op.key, sort_keys=True, default=str)
            if marker in seen:
                raise HTTPException(422, "A record can only appear once in a batch.")
            seen.add(marker)
            blocked = IMMUTABLE | primary | OWNERSHIP_FIELDS
        blocked |= {c.name for c in table.c if c.computed or c.identity}
        if not set(op.values) <= visible - blocked:
            raise HTTPException(
                422, "A field is protected, unknown, or cannot be reassigned."
            )
        if op.action == "delete" and op.values:
            raise HTTPException(422, "Delete operations must not contain new values.")
        if op.action != "delete" and not op.values:
            raise HTTPException(422, "Supply at least one field.")
        if table.name == "farmers":
            if op.action == "create":
                raise HTTPException(
                    422,
                    "Accounts must register through verified sign-in. Administrators can update existing profiles.",
                )
            if "status" in op.values and op.values["status"] not in (
                "active",
                "onboarding",
                "suspended",
            ):
                raise HTTPException(
                    422, "Use active, onboarding or suspended account status."
                )


def refuse_linked_delete(db, table, row):
    # Do not silently cascade into another resource, even if its FK permits it.
    inspector = inspect(db)
    for name in inspector.get_table_names(schema="sv3"):
        for fk in inspector.get_foreign_keys(name, schema="sv3"):
            if fk["referred_table"] != table.name or fk.get("referred_schema") not in (
                None,
                "sv3",
            ):
                continue
            if fk.get("options", {}).get("ondelete", "").upper() in (
                "CASCADE",
                "SET NULL",
                "SET DEFAULT",
            ):
                raise HTTPException(
                    409,
                    f"Deletion could affect linked {name} records. Use a status change instead. Cascading deletes are not available in this panel.",
                )
            # Restrictive foreign keys are enforced by PostgreSQL at execution.


def apply_batch(db, table, batch, actor):
    validate_batch(table, batch, actor)
    changes = []
    for op in batch.operations:
        before = None
        if op.action != "create":
            condition = and_(*(table.c[k] == v for k, v in op.key.items()))
            before = (
                db.execute(select(table).where(condition).with_for_update())
                .mappings()
                .first()
            )
            if before is None or digest(before) != op.version:
                raise HTTPException(
                    409,
                    "A record changed or was removed. Refresh and review a new preview.",
                )
        if op.action == "delete":
            refuse_linked_delete(db, table, before)
            db.execute(table.delete().where(condition))
            after = None
        else:
            values = dict(op.values)
            if (
                table.name == "farmers"
                and {"contact_phone", "contact_email"} & values.keys()
            ):
                values["contact_verified_at"] = None
            if op.action == "update":
                if "row_version" in table.c:
                    values["row_version"] = table.c.row_version + 1
                if "updated_at" in table.c:
                    values["updated_at"] = func.now()
            statement = (
                table.insert().values(**values)
                if op.action == "create"
                else table.update().where(condition).values(**values)
            )
            after = db.execute(statement.returning(*table.c)).mappings().one()
            if table.name == "farmers" and values.get("status") == "suspended":
                db.execute(
                    text(
                        "UPDATE sv3.assistant_sessions SET revoked_at=now(),run_token=NULL,run_expires_at=NULL WHERE farmer_id=:id"
                    ),
                    {"id": before["id"]},
                )
        changes.append(
            {
                "action": op.action,
                "key": clean(
                    {
                        c.name: (after if after is not None else before)[c.name]
                        for c in table.primary_key
                    }
                ),
                "before": clean(dict(before)) if before is not None else None,
                "after": clean(dict(after)) if after is not None else None,
            }
        )
    return changes


@router.post("/resources/{name}/preview")
def preview(name: str, batch: Batch, actor=ADMIN_ACCESS):
    with connection() as db:
        table = table_for(db, name)
        # Execute against real constraints and roll back every proposed write.
        savepoint = db.begin_nested()
        try:
            changes = apply_batch(db, table, batch, actor)
        finally:
            savepoint.rollback()
        pid = str(uuid.uuid4())
        expires = datetime.now(UTC) + timedelta(minutes=10)
        db.execute(
            text(
                "DELETE FROM sv3.admin_previews WHERE expires_at < now() - interval '1 day'"
            )
        )
        db.execute(
            text(
                "INSERT INTO sv3.admin_previews(id,actor,resource,payload,expires_at) VALUES(:id,:actor,:resource,CAST(:payload AS jsonb),:expires)"
            ),
            {
                "id": pid,
                "actor": actor["subject"],
                "resource": name,
                "payload": batch.model_dump_json(),
                "expires": expires,
            },
        )
        return {
            "id": pid,
            "expires_at": str(expires),
            "changes": changes,
            "confirmation": f"APPLY {len(changes)}",
            "notice": "Nothing has been saved. Generated IDs and timestamps are assigned when applied.",
        }


@router.post("/previews/{preview_id}/commit")
def commit(preview_id: uuid.UUID, body: Commit, actor=ADMIN_ACCESS):
    with connection() as db:
        row = (
            db.execute(
                text(
                    "SELECT * FROM sv3.admin_previews WHERE id=:id AND actor=:actor FOR UPDATE"
                ),
                {"id": preview_id, "actor": actor["subject"]},
            )
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "Preview not found for this administrator.")
        if row["committed_at"]:
            return {"status": "already_applied", "id": str(preview_id)}
        if row["expires_at"] < datetime.now(UTC):
            raise HTTPException(409, "Preview expired. Review the changes again.")
        batch = Batch.model_validate(row["payload"])
        if body.confirmation != f"APPLY {len(batch.operations)}":
            raise HTTPException(
                422, "Type the exact confirmation shown in the preview."
            )
        changes = apply_batch(db, table_for(db, row["resource"]), batch, actor)
        # Retain keys and hashes, not duplicate private profile data in the audit.
        summary = [
            {
                "action": c["action"],
                "key": c["key"],
                "fields": list(op.values),
                "before_hash": digest(c["before"]) if c["before"] else None,
                "after_hash": digest(c["after"]) if c["after"] else None,
            }
            for c, op in zip(changes, batch.operations)
        ]
        db.execute(
            text(
                "INSERT INTO sv3.admin_audit(id,actor,role,resource,reason,changes) VALUES(:id,:actor,:role,:resource,:reason,CAST(:changes AS jsonb))"
            ),
            {
                "id": preview_id,
                "actor": actor["subject"],
                "role": actor["role"],
                "resource": row["resource"],
                "reason": batch.reason,
                "changes": json.dumps(summary),
            },
        )
        db.execute(
            text(
                "UPDATE sv3.admin_previews SET committed_at=now(),payload='{}'::jsonb WHERE id=:id"
            ),
            {"id": preview_id},
        )
        return {"status": "applied", "id": str(preview_id), "count": len(changes)}


@router.get("/audit")
def audit(page: int = Query(1, ge=1), actor=ADMIN_ACCESS):
    with connection() as db:
        rows = (
            db.execute(
                text(
                    "SELECT * FROM sv3.admin_audit ORDER BY created_at DESC,id DESC LIMIT 25 OFFSET :offset"
                ),
                {"offset": (page - 1) * 25},
            )
            .mappings()
            .all()
        )
        total = db.execute(text("SELECT count(*) FROM sv3.admin_audit")).scalar_one()
        return {"records": [clean(dict(r)) for r in rows], "total": total}
