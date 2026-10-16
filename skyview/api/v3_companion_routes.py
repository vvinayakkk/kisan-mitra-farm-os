"""Owned companion settings and receipts from real bounded in-app follow-ups."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text

from skyview.api.v3_routes import Owner
from skyview.data.v3 import db, repository

router = APIRouter(prefix="/api/companion", tags=["Farm companion"])


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    row_version: int = Field(ge=1)
    name: str = Field(default="Saathi", min_length=1, max_length=40)
    enabled: bool
    frequency_hours: int = Field(default=6, ge=1, le=168)
    quiet_start: int = Field(default=22, ge=0, le=23)
    quiet_end: int = Field(default=6, ge=0, le=23)
    timezone: str = Field(default="Asia/Kolkata", max_length=80)

    @field_validator("timezone")
    @classmethod
    def timezone_known(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Choose a valid timezone") from exc
        return value


def _ensure(conn, owner):
    conn.execute(
        text(
            "INSERT INTO sv3.companion_preferences(farmer_id) VALUES(:owner) ON CONFLICT DO NOTHING"
        ),
        {"owner": owner},
    )


@router.get("")
def summary(owner: Owner):

    with db.connection(owner, write=True) as conn:
        _ensure(conn, owner)
        settings = repository.rows(
            conn,
            "SELECT * FROM sv3.companion_preferences WHERE farmer_id=:owner",
            {"owner": owner},
        )[0]
        activity = repository.rows(
            conn,
            "SELECT id,scheduled_at AS created_at,status,payload FROM sv3.notifications WHERE payload->>'source'='companion' ORDER BY scheduled_at DESC,id DESC LIMIT 30",
        )
        outputs = repository.rows(
            conn,
            "SELECT id,title,format,bytes,created_at,preview FROM sv3.artifacts ORDER BY created_at DESC LIMIT 6",
        )
        prepared = repository.rows(
            conn,
            "SELECT * FROM (SELECT DISTINCT ON (area) id,area,title,summary,steps,evidence,research,status,row_version,mission_id,created_at,updated_at FROM sv3.companion_proposals WHERE status IN ('ready','approved') ORDER BY area,updated_at DESC,id DESC) latest ORDER BY updated_at DESC,id DESC LIMIT 6",
        )
        from skyview.api.v3_whatsapp_routes import channel_summary

        whatsapp = channel_summary(conn)
        heartbeat = conn.execute(
            text("SELECT last_sweep_at FROM sv3.companion_worker_state WHERE singleton")
        ).scalar()
    now = datetime.now(UTC)
    local = now.astimezone(ZoneInfo(settings["timezone"]))
    start, end = settings["quiet_start"], settings["quiet_end"]
    quiet = (start < end and start <= local.hour < end) or (
        start > end and (local.hour >= start or local.hour < end)
    )
    running = bool(heartbeat and heartbeat > now - timedelta(minutes=3))
    status = (
        "paused"
        if not settings["enabled"]
        else "quiet_hours"
        if quiet
        else "watching"
        if running
        else "waiting_for_worker"
    )
    return {
        "name": settings["name"],
        "settings": settings,
        "status": status,
        "worker_last_seen_at": heartbeat,
        "activity": [
            {
                "id": item["id"],
                "status": item["status"],
                "created_at": item["created_at"],
                **item["payload"],
            }
            for item in activity
        ],
        "outputs": outputs,
        "prepared": prepared,
        "channels": {
            "in_app": {"connected": True, "enabled": settings["enabled"]},
            "whatsapp": whatsapp,
            "sms": {"connected": False, "enabled": False},
        },
        "scope": ["Due farm tasks", "Open crop follow-ups", "Reviewable farm plans"],
        "weather_monitoring": False,
    }


@router.patch("/preferences")
def preferences(body: Preferences, owner: Owner):
    with db.connection(owner, write=True) as conn:
        _ensure(conn, owner)
        result = conn.execute(
            text("""UPDATE sv3.companion_preferences SET name=:name,enabled=:enabled,frequency_hours=:frequency_hours,
         quiet_start=:quiet_start,quiet_end=:quiet_end,timezone=:timezone,row_version=row_version+1,updated_at=now(),next_check_at=now()
         WHERE farmer_id=:owner AND row_version=:row_version RETURNING row_version"""),
            {**body.model_dump(), "owner": owner},
        ).scalar()
        if result is None:
            raise HTTPException(
                409, "Your companion settings changed. Refresh and try again."
            )
    from skyview.data.v3.worker import notify_companion

    notify_companion()
    return summary(owner)


@router.post("/activity/{identifier}/read")
def mark_read(identifier: str, owner: Owner):
    import uuid

    try:
        uuid.UUID(identifier)
    except ValueError as exc:
        raise HTTPException(404, "Activity unavailable") from exc
    with db.connection(owner, write=True) as conn:
        changed = conn.execute(
            text(
                "UPDATE sv3.notifications SET status='read' WHERE id=:id AND payload->>'source'='companion' RETURNING id"
            ),
            {"id": identifier},
        ).scalar()
        if changed is None:
            raise HTTPException(404, "Activity unavailable")
    return {"status": "read"}


Area = Literal["today", "markets", "schemes", "records", "crops", "exchange"]


class PrepareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    area: Area = "today"
    research: bool = False


class ProposalReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    row_version: int = Field(ge=1)
    action: Literal["approve", "edit", "dismiss"]
    title: str | None = Field(default=None, min_length=2, max_length=160)
    steps: list[str] | None = Field(default=None, min_length=1, max_length=12)

    @field_validator("steps")
    @classmethod
    def valid_steps(cls, values):
        if values is not None:
            values = [value.strip() for value in values]
            if any(not value or len(value) > 160 for value in values):
                raise ValueError("Each plan step must contain 1–160 characters.")
        return values


@router.get("/proposals")
def proposals(owner: Owner, area: Area = "today"):
    with db.connection(owner) as conn:
        items = repository.rows(
            conn,
            "SELECT * FROM sv3.companion_proposals WHERE area=:area AND status<>'dismissed' ORDER BY created_at DESC,id DESC LIMIT 5",
            {"area": area},
        )
        jobs = repository.rows(
            conn,
            "SELECT id,state,research,created_at,finished_at,safe_error FROM sv3.companion_jobs WHERE area=:area ORDER BY created_at DESC LIMIT 1",
            {"area": area},
        )
    return {"proposals": items, "job": jobs[0] if jobs else None}


@router.post("/prepare", status_code=202)
def prepare(body: PrepareRequest, owner: Owner):
    with db.connection(owner, write=True) as conn:
        conn.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))"),
            {"scope": f"{owner}:{body.area}"},
        )
        active = repository.rows(
            conn,
            "SELECT id,state FROM sv3.companion_jobs WHERE area=:area AND (state IN ('queued','running') OR (state='done' AND created_at>now()-interval '30 seconds' AND research=:research)) ORDER BY created_at DESC LIMIT 1",
            {"area": body.area, "research": body.research},
        )
        if active and body.research and active[0]["state"] in {"queued", "running"}:
            conn.execute(
                text("UPDATE sv3.companion_jobs SET research=true WHERE id=:id"),
                {"id": active[0]["id"]},
            )
        job = (
            active[0]
            if active
            else repository.rows(
                conn,
                "INSERT INTO sv3.companion_jobs(farmer_id,area,research) VALUES(:owner,:area,:research) RETURNING id,state",
                {"owner": owner, **body.model_dump()},
            )[0]
        )
    from skyview.data.v3.worker import notify_companion

    notify_companion()
    return job


@router.post("/proposals/{identifier}/review")
def review_proposal(identifier: uuid.UUID, body: ProposalReview, owner: Owner):
    with db.connection(owner, write=True) as conn:
        rows = repository.rows(
            conn,
            "SELECT * FROM sv3.companion_proposals WHERE id=:id FOR UPDATE",
            {"id": str(identifier)},
        )
        if not rows:
            raise HTTPException(404, "This suggestion is unavailable.")
        item = rows[0]

        if item["status"] == "approved" and body.action == "approve":
            return {"proposal": item, "mission_id": item["mission_id"]}
        if item["row_version"] != body.row_version or item["status"] != "ready":
            raise HTTPException(
                409, "This suggestion changed. Refresh before reviewing."
            )
        title = body.title or item["title"]
        steps = (
            [{"title": value, "done": False} for value in body.steps]
            if body.steps
            else item["steps"]
        )
        mission = None
        status = "dismissed" if body.action == "dismiss" else "ready"
        if body.action == "approve":
            mission = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO sv3.farm_missions(id,farmer_id,title,objective,steps,status) VALUES(:id,:owner,:title,:objective,CAST(:steps AS jsonb),'active')"
                ),
                {
                    "id": mission,
                    "owner": owner,
                    "title": title,
                    "objective": item["summary"],
                    "steps": json.dumps(steps),
                },
            )
            conn.execute(
                text(
                    "INSERT INTO sv3.mission_receipts(farmer_id,mission_id,action,detail) VALUES(:owner,:mission,'approved_proposal',:detail)"
                ),
                {
                    "owner": owner,
                    "mission": mission,
                    "detail": f"Reviewed Saathi suggestion {identifier}. Saved as a plan; field work has not been performed.",
                },
            )
            conn.execute(
                text("""INSERT INTO sv3.notifications
                    (farmer_id,channel,delivery_allowed,scheduled_at,status,payload,dedupe_key)
                    VALUES(:owner,'in_app',true,now(),'ready',CAST(:payload AS jsonb),:key)
                    ON CONFLICT(farmer_id,dedupe_key) DO NOTHING"""),
                {
                    "owner": owner,
                    "key": f"companion:approved:{identifier}",
                    "payload": json.dumps(
                        {
                            "source": "companion",
                            "kind": "plan_saved",
                            "title": "Your plan is ready",
                            "detail": f"{title} — saved to your farm notebook.",
                            "href": f"/workspace?view=records&tab=missions&mission={mission}",
                            "proposal_id": str(identifier),
                            "mission_id": mission,
                        }
                    ),
                },
            )
            status = "approved"
        updated = repository.rows(
            conn,
            "UPDATE sv3.companion_proposals SET title=:title,steps=CAST(:steps AS jsonb),status=:status,mission_id=:mission,row_version=row_version+1,updated_at=now() WHERE id=:id RETURNING *",
            {
                "id": str(identifier),
                "title": title,
                "steps": json.dumps(steps),
                "status": status,
                "mission": mission,
            },
        )[0]
    return {"proposal": updated, "mission_id": mission}
