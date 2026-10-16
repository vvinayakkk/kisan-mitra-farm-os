"""Persistent farmer-controlled workspace workflows; no pretend execution or diagnosis."""

import json
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from skyview.api.v3_routes import Owner
from skyview.data.v3 import db, repository

router = APIRouter(prefix="/api/farm-workspace", tags=["Farmer workspace"])


_tool_connection = ContextVar("workflow_tool_connection", default=None)


@contextmanager
def connection_scope(owner, write=False):
    active = _tool_connection.get()
    if active is not None:
        if str(active[0]) != str(owner):
            raise RuntimeError("Workflow execution owner mismatch")
        yield active[1]
    else:
        with db.connection(owner, write=write) as connection:
            yield connection


def india_today():
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


class Input(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False
    )


class LedgerInput(Input):
    description: str = Field(min_length=2, max_length=200)
    category: str = Field(min_length=1, max_length=60)
    kind: Literal["income", "expense"]
    basis: Literal["actual", "estimated", "receivable"]
    amount_inr: Decimal = Field(gt=0, le=100000000, max_digits=14, decimal_places=2)
    occurred_on: date
    notes: str = Field(default="", max_length=2000)
    cycle_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def receivable_income(self):
        if self.basis == "receivable" and self.kind != "income":
            raise ValueError("Only income can be a receivable")
        if self.basis == "actual" and self.occurred_on > india_today():
            raise ValueError(
                "An actual payment or expense cannot be dated in the future"
            )
        return self


class LedgerEdit(LedgerInput):
    row_version: int = Field(ge=1)


class CaseInput(Input):
    title: str = Field(min_length=2, max_length=160)
    cycle_id: uuid.UUID | None = None
    note: str = Field(default="", max_length=4000)


class CaseEdit(Input):
    row_version: int = Field(ge=1)
    title: str = Field(min_length=2, max_length=160)
    status: Literal["open", "monitoring", "expert_review", "resolved"]


class CaseNote(Input):
    note: str = Field(min_length=1, max_length=4000)
    observed_on: date


class MissionStep(Input):
    title: str = Field(min_length=1, max_length=160)
    done: bool = False


class MissionInput(Input):
    title: str = Field(min_length=2, max_length=160)
    objective: str = Field(default="", max_length=2000)
    steps: list[MissionStep] = Field(default_factory=list, max_length=30)


class MissionEdit(MissionInput):
    row_version: int = Field(ge=1)
    status: Literal["draft", "active", "paused", "completed", "cancelled"]


class MemoryEdit(Input):
    value: str = Field(min_length=1, max_length=2000)


def records(connection, sql, params=None):
    return [
        repository.clean(dict(row))
        for row in connection.execute(text(sql), params or {}).mappings()
    ]


def one(connection, sql, params):
    items = records(connection, sql, params)
    if not items:
        raise HTTPException(404, "Record not found")
    return items[0]


def versioned(connection, table, identifier, version):
    # table is a call-site constant; never sourced from HTTP input.
    row = one(
        connection,
        f"SELECT * FROM sv3.{table} WHERE id=:id FOR UPDATE",
        {"id": str(identifier)},
    )
    if row["row_version"] != version:
        raise HTTPException(409, "This record changed. Refresh before editing.")
    if row.get("deleted_at"):
        raise HTTPException(404, "Record not found")
    return row


def inputs(body):
    return {
        k: str(v) if isinstance(v, uuid.UUID) else v
        for k, v in body.model_dump().items()
    }


def summary(connection):
    values = records(
        connection,
        """SELECT kind,basis,sum(amount_inr) amount FROM sv3.ledger_entries
      WHERE deleted_at IS NULL GROUP BY kind,basis""",
    )
    out = {
        "actual_income": 0,
        "actual_expense": 0,
        "estimated_income": 0,
        "estimated_expense": 0,
        "receivable": 0,
    }
    for row in values:
        key = (
            "receivable"
            if row["basis"] == "receivable"
            else f"{row['basis']}_{row['kind']}"
        )
        out[key] = row["amount"]
    out["recorded_balance"] = out["actual_income"] - out["actual_expense"]
    out["includes_demo_fixtures"] = bool(
        connection.execute(
            text(
                "SELECT EXISTS(SELECT 1 FROM sv3.ledger_entries WHERE deleted_at IS NULL AND origin='synthetic')"
            )
        ).scalar()
    )
    out["currency"] = "INR"
    out["note"] = (
        "Recorded entries only; missing costs and sales are not inferred. Receivables and estimates are excluded from recorded balance."
    )
    return out


@router.get("/ledger")
def ledger(
    owner: Owner,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100000),
):
    with connection_scope(owner) as connection:
        return {
            "items": records(
                connection,
                "SELECT * FROM sv3.ledger_entries WHERE deleted_at IS NULL ORDER BY occurred_on DESC,created_at DESC LIMIT :n OFFSET :o",
                {"n": limit, "o": offset},
            ),
            "summary": summary(connection),
        }


@router.post("/ledger")
def add_ledger(body: LedgerInput, owner: Owner):
    try:
        with connection_scope(owner, write=True) as connection:
            return one(
                connection,
                """INSERT INTO sv3.ledger_entries(farmer_id,cycle_id,description,category,kind,basis,amount_inr,occurred_on,notes)
              VALUES(:owner,:cycle_id,:description,:category,:kind,:basis,:amount_inr,:occurred_on,:notes) RETURNING *""",
                {**inputs(body), "owner": owner},
            )
    except IntegrityError as exc:
        raise HTTPException(422, "Choose an owned crop cycle") from exc


@router.patch("/ledger/{identifier}")
def edit_ledger(identifier: uuid.UUID, body: LedgerEdit, owner: Owner):
    try:
        with connection_scope(owner, write=True) as connection:
            versioned(connection, "ledger_entries", identifier, body.row_version)
            return one(
                connection,
                """UPDATE sv3.ledger_entries SET cycle_id=:cycle_id,description=:description,category=:category,
              kind=:kind,basis=:basis,amount_inr=:amount_inr,occurred_on=:occurred_on,notes=:notes,
              row_version=row_version+1,updated_at=now() WHERE id=:id RETURNING *""",
                {**inputs(body), "id": str(identifier)},
            )
    except IntegrityError as exc:
        raise HTTPException(422, "Choose an owned crop cycle") from exc


@router.delete("/ledger/{identifier}")
def remove_ledger(identifier: uuid.UUID, owner: Owner, row_version: int = Query(ge=1)):
    with connection_scope(owner, write=True) as connection:
        versioned(connection, "ledger_entries", identifier, row_version)
        connection.execute(
            text(
                "UPDATE sv3.ledger_entries SET deleted_at=now(),row_version=row_version+1,updated_at=now() WHERE id=:id"
            ),
            {"id": str(identifier)},
        )
    return {"deleted": True}


@router.get("/cases")
def cases(owner: Owner, limit: int = Query(100, ge=1, le=200)):
    with connection_scope(owner) as connection:
        return {
            "items": records(
                connection,
                """SELECT c.id,c.title,c.status,c.cycle_id,c.assessment,c.model_version,c.clinician_label,c.created_at,c.updated_at,c.row_version,
           (SELECT count(*) FROM sv3.crop_case_notes n WHERE n.case_id=c.id) note_count,
           CASE WHEN c.image_uri='no-image-submitted' THEN false ELSE true END has_image
           FROM sv3.disease_cases c ORDER BY c.updated_at DESC LIMIT :n""",
                {"n": limit},
            ),
            "note": "Model assessments are uncertain. Farmer follow-up records do not establish a clinical diagnosis.",
        }


@router.post("/cases")
def add_case(body: CaseInput, owner: Owner):
    try:
        with connection_scope(owner, write=True) as connection:
            result = one(
                connection,
                """INSERT INTO sv3.disease_cases(farmer_id,cycle_id,title,image_uri,image_hash,status)
              VALUES(:owner,:cycle_id,:title,'no-image-submitted','','open') RETURNING id,title,status,cycle_id,row_version,created_at""",
                {**inputs(body), "owner": owner},
            )
            if body.note:
                connection.execute(
                    text(
                        "INSERT INTO sv3.crop_case_notes(farmer_id,case_id,note,observed_on) VALUES(:owner,:id,:note,current_date)"
                    ),
                    {"owner": owner, "id": result["id"], "note": body.note},
                )
            return result
    except IntegrityError as exc:
        raise HTTPException(422, "Choose an owned crop cycle") from exc


@router.patch("/cases/{identifier}")
def edit_case(identifier: uuid.UUID, body: CaseEdit, owner: Owner):
    with connection_scope(owner, write=True) as connection:
        versioned(connection, "disease_cases", identifier, body.row_version)
        return one(
            connection,
            "UPDATE sv3.disease_cases SET title=:title,status=:status,row_version=row_version+1,updated_at=now() WHERE id=:id RETURNING id,title,status,row_version",
            {**inputs(body), "id": str(identifier)},
        )


@router.get("/cases/{identifier}/notes")
def case_notes(identifier: uuid.UUID, owner: Owner):
    with connection_scope(owner) as connection:
        one(
            connection,
            "SELECT id FROM sv3.disease_cases WHERE id=:id",
            {"id": str(identifier)},
        )
        return {
            "items": records(
                connection,
                "SELECT id,note,observed_on,created_at FROM sv3.crop_case_notes WHERE case_id=:id ORDER BY created_at DESC LIMIT 200",
                {"id": str(identifier)},
            )
        }


@router.post("/cases/{identifier}/notes")
def add_note(identifier: uuid.UUID, body: CaseNote, owner: Owner):
    if body.observed_on > india_today():
        raise HTTPException(422, "An observation cannot be in the future")
    with connection_scope(owner, write=True) as connection:
        one(
            connection,
            "SELECT id FROM sv3.disease_cases WHERE id=:id FOR UPDATE",
            {"id": str(identifier)},
        )
        result = one(
            connection,
            "INSERT INTO sv3.crop_case_notes(farmer_id,case_id,note,observed_on) VALUES(:owner,:id,:note,:observed_on) RETURNING *",
            {**inputs(body), "owner": owner, "id": str(identifier)},
        )
        connection.execute(
            text(
                "UPDATE sv3.disease_cases SET updated_at=now(),row_version=row_version+1 WHERE id=:id"
            ),
            {"id": str(identifier)},
        )
        return result


@router.get("/missions")
def missions(owner: Owner, limit: int = Query(100, ge=1, le=200)):
    with connection_scope(owner) as connection:
        return {
            "items": records(
                connection,
                "SELECT * FROM sv3.farm_missions ORDER BY updated_at DESC LIMIT :n",
                {"n": limit},
            ),
            "note": "Farmer-controlled checklists. State changes record your intent; no device command, message, booking or external execution is implied.",
        }


def receipt(connection, owner, identifier, action, detail):
    connection.execute(
        text(
            "INSERT INTO sv3.mission_receipts(farmer_id,mission_id,action,detail) VALUES(:owner,:id,:action,:detail)"
        ),
        {"owner": owner, "id": identifier, "action": action, "detail": detail},
    )


@router.post("/missions")
def add_mission(body: MissionInput, owner: Owner):
    with connection_scope(owner, write=True) as connection:
        result = one(
            connection,
            "INSERT INTO sv3.farm_missions(farmer_id,title,objective,steps) VALUES(:owner,:title,:objective,CAST(:steps AS jsonb)) RETURNING *",
            {
                "owner": owner,
                "title": body.title,
                "objective": body.objective,
                "steps": json.dumps([step.model_dump() for step in body.steps]),
            },
        )
        receipt(
            connection,
            owner,
            result["id"],
            "created",
            "Plan saved by the farmer; no external action performed.",
        )
        return result


@router.patch("/missions/{identifier}")
def edit_mission(identifier: uuid.UUID, body: MissionEdit, owner: Owner):
    transitions = {
        "draft": {"draft", "active", "cancelled"},
        "active": {"active", "paused", "completed", "cancelled"},
        "paused": {"paused", "active", "cancelled"},
        "completed": {"completed"},
        "cancelled": {"cancelled"},
    }
    with connection_scope(owner, write=True) as connection:
        before = versioned(connection, "farm_missions", identifier, body.row_version)
        if body.status not in transitions[before["status"]]:
            raise HTTPException(409, "This mission transition is unavailable")
        if before["status"] in ("completed", "cancelled"):
            raise HTTPException(
                409, "Finished missions are read-only; create a new plan"
            )
        if body.status == "completed" and (
            not body.steps or not all(step.done for step in body.steps)
        ):
            raise HTTPException(
                422, "Confirm every checklist step before recording completion"
            )
        result = one(
            connection,
            "UPDATE sv3.farm_missions SET title=:title,objective=:objective,steps=CAST(:steps AS jsonb),status=:status,row_version=row_version+1,updated_at=now() WHERE id=:id RETURNING *",
            {
                "id": str(identifier),
                "title": body.title,
                "objective": body.objective,
                "steps": json.dumps([step.model_dump() for step in body.steps]),
                "status": body.status,
            },
        )
        receipt(
            connection,
            owner,
            str(identifier),
            body.status,
            f"Farmer updated plan from {before['status']} to {body.status}; checklist completion is self-reported, not hardware-verified.",
        )
        return result


@router.get("/missions/{identifier}/receipts")
def receipts(identifier: uuid.UUID, owner: Owner):
    with connection_scope(owner) as connection:
        one(
            connection,
            "SELECT id FROM sv3.farm_missions WHERE id=:id",
            {"id": str(identifier)},
        )
        return {
            "items": records(
                connection,
                "SELECT id,action,detail,created_at FROM sv3.mission_receipts WHERE mission_id=:id ORDER BY created_at DESC LIMIT 200",
                {"id": str(identifier)},
            )
        }


@router.get("/memories")
def memories(owner: Owner):
    from skyview.assistant.memory_facts import extract_facts

    with connection_scope(owner) as connection:
        items = records(
            connection,
            "SELECT id,fact_key,value,search_text,confidence,valid_from,evidence_message_id FROM sv3.memories WHERE valid_to IS NULL ORDER BY valid_from DESC LIMIT 200",
        )
        return {
            "items": [
                item
                for item in items
                if not item["fact_key"].startswith("user_statement:")
                or extract_facts(item["search_text"])
            ],
            "note": "Facts retained from your conversations. Corrections supersede previous values; forgetting excludes them from future recall.",
        }


@router.patch("/memories/{identifier}")
def correct_memory(identifier: uuid.UUID, body: MemoryEdit, owner: Owner):
    with connection_scope(owner, write=True) as connection:
        old = one(
            connection,
            "SELECT * FROM sv3.memories WHERE id=:id AND valid_to IS NULL FOR UPDATE",
            {"id": str(identifier)},
        )
        connection.execute(
            text(
                "UPDATE sv3.memories SET valid_to=GREATEST(now(),valid_from+interval '1 microsecond') WHERE id=:id"
            ),
            {"id": str(identifier)},
        )
        return one(
            connection,
            """INSERT INTO sv3.memories(farmer_id,fact_key,value,confidence,valid_from,supersedes_id,search_text)
          VALUES(:owner,:key,CAST(:value AS jsonb),1,now(),:id,:content) RETURNING id,fact_key,value,valid_from,search_text""",
            {
                "owner": owner,
                "key": old["fact_key"],
                "value": json.dumps(
                    {"content": body.value, "source": "farmer correction"}
                ),
                "id": str(identifier),
                "content": body.value,
            },
        )


@router.delete("/memories/{identifier}")
def forget_memory(identifier: uuid.UUID, owner: Owner):
    with connection_scope(owner, write=True) as connection:
        one(
            connection,
            "SELECT id FROM sv3.memories WHERE id=:id AND valid_to IS NULL FOR UPDATE",
            {"id": str(identifier)},
        )
        connection.execute(
            text(
                "UPDATE sv3.memories SET valid_to=GREATEST(now(),valid_from+interval '1 microsecond') WHERE id=:id"
            ),
            {"id": str(identifier)},
        )
    return {
        "forgotten": True,
        "note": "Excluded from durable fact recall. Original conversation messages remain until separately deleted.",
    }


@router.get("/timeline")
def timeline(owner: Owner, limit: int = Query(60, ge=1, le=200)):
    with connection_scope(owner) as connection:
        return {
            "items": records(
                connection,
                """SELECT * FROM (
          SELECT id,'ledger' kind,description title,updated_at occurred_at,jsonb_build_object('basis',basis,'kind',kind,'amount_inr',amount_inr) detail FROM sv3.ledger_entries WHERE deleted_at IS NULL
          UNION ALL SELECT id,'crop_case',title,updated_at,jsonb_build_object('status',status) FROM sv3.disease_cases
          UNION ALL SELECT id,'mission',title,updated_at,jsonb_build_object('status',status) FROM sv3.farm_missions
          UNION ALL SELECT fo.id,'field_observation',fo.type,fo.observed_at,jsonb_build_object('observation',fo.observation,'origin',fo.origin,'cycle_id',fo.cycle_id) FROM sv3.field_observations fo
          UNION ALL SELECT ss.id,'soil_report',COALESCE(ss.lab_name,'Soil report'),ss.sampled_on::timestamp AT TIME ZONE 'Asia/Kolkata',jsonb_build_object('sample_type',ss.sample_type,'plot_id',ss.plot_id,'lab_verified',false) FROM sv3.soil_samples ss
          UNION ALL SELECT cc.id,'crop_cycle',c.name||' · '||cc.season,cc.sowing_date::timestamp AT TIME ZONE 'Asia/Kolkata',jsonb_build_object('status',cc.status,'plot_id',cc.plot_id,'entry_type','reported_sowing_date') FROM sv3.crop_cycles cc JOIN sv3.crops c ON c.id=cc.crop_id
          UNION ALL SELECT id,'calendar',title,due_at,jsonb_build_object('status',status,'entry_type','planned_due_date') FROM sv3.tasks WHERE deleted_at IS NULL
          ) e WHERE occurred_at<=now() ORDER BY occurred_at DESC LIMIT :n""",
                {"n": limit},
            ),
            "planned": records(
                connection,
                """SELECT id,'calendar' kind,title,due_at occurred_at,jsonb_build_object('status',status,'entry_type','future_plan') detail FROM sv3.tasks WHERE deleted_at IS NULL AND status='open' AND due_at>now() ORDER BY due_at LIMIT 20""",
            ),
            "note": "Dated history is separated from upcoming calendar plans; entries are not evidence of physical execution.",
        }


@router.get("/today")
def today(owner: Owner):
    with connection_scope(owner) as connection:
        tasks = records(
            connection,
            "SELECT id,title,due_at FROM sv3.tasks WHERE deleted_at IS NULL AND status='open' AND due_at<((date_trunc('day',now() AT TIME ZONE 'Asia/Kolkata')+interval '1 day') AT TIME ZONE 'Asia/Kolkata') ORDER BY due_at LIMIT 3",
        )
        counts = {
            "tasks": connection.execute(
                text(
                    "SELECT count(*) FROM sv3.tasks WHERE deleted_at IS NULL AND status='open'"
                )
            ).scalar(),
            "cases": connection.execute(
                text("SELECT count(*) FROM sv3.disease_cases WHERE status<>'resolved'")
            ).scalar(),
            "missions": connection.execute(
                text(
                    "SELECT count(*) FROM sv3.farm_missions WHERE status IN ('active','paused')"
                )
            ).scalar(),
        }
        actions = [
            {
                "id": t["id"],
                "title": t["title"],
                "detail": f"Your saved task is due {t['due_at']}",
                "kind": "task",
                "priority": 1,
                "href": "calendar",
            }
            for t in tasks
        ]
        if counts["cases"]:
            actions.append(
                {
                    "id": "crop-followup",
                    "title": "Check your crop follow-ups",
                    "detail": f"{counts['cases']} open observations or photo assessments",
                    "kind": "crop_case",
                    "priority": 2,
                    "href": "records",
                }
            )
        if not actions:
            actions.append(
                {
                    "id": "plan-day",
                    "title": "Plan today's farm work",
                    "detail": "Add a task or record a field observation. Mitra can help you prepare a plan.",
                    "kind": "suggestion",
                    "priority": 3,
                    "href": "chat",
                }
            )
        return {
            "actions": actions[:3],
            "counts": counts,
            "ledger": summary(connection),
            "provenance": {
                "origin": "synthetic" if db.mode() == "v3_demo" else "user_reported",
                "note": "Demo mode may include fictional farm records. Priorities use saved due dates and unresolved cases. This is a planning aid, not an agronomic diagnosis.",
            },
        }


def execute_tool(name, arguments, owner, execution_id):
    """Approval worker bridge: one atomic transaction for records and replay receipt.

    Kept outside the HTTP signature. Repeated calls return the original committed
    result, including after process failure; the same key cannot change arguments.
    """
    import hashlib

    from skyview.api import v3_shared_work_routes as shared

    dispatch = {
        "record_service": (shared.Service, shared.create_service),
        "create_farm_group": (shared.GroupInput, shared.create_group),
        "record_ledger": (LedgerInput, add_ledger),
        "create_crop_case": (CaseInput, add_case),
        "create_mission": (MissionInput, add_mission),
    }
    if not execution_id or len(str(execution_id)) > 200:
        raise ValueError("An execution ID is required")
    encoded = json.dumps(arguments, sort_keys=True, ensure_ascii=False, default=str)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{owner}:{name}:{execution_id}"))
    with db.connection(owner, write=True) as connection:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": key}
        )
        prior = records(
            connection,
            "SELECT argument_hash,result FROM sv3.workflow_tool_executions WHERE id=:id",
            {"id": key},
        )
        if prior:
            if prior[0]["argument_hash"] != digest:
                raise HTTPException(
                    409, "An execution ID cannot change approved arguments"
                )
            return prior[0]["result"]
        token = _tool_connection.set((owner, connection))
        try:
            if name in dispatch:
                model, function = dispatch[name]
                result = function(model.model_validate(arguments), owner)
            elif name == "create_shared_task":
                result = shared.create_task(
                    uuid.UUID(arguments["group_id"]),
                    shared.SharedTask.model_validate(
                        {k: v for k, v in arguments.items() if k != "group_id"}
                    ),
                    owner,
                )
            elif name == "add_crop_note":
                result = add_note(
                    uuid.UUID(arguments["case_id"]),
                    CaseNote.model_validate(
                        {k: v for k, v in arguments.items() if k != "case_id"}
                    ),
                    owner,
                )
            elif name == "correct_farmer_memory":
                result = correct_memory(
                    uuid.UUID(arguments["memory_id"]),
                    MemoryEdit.model_validate({"value": arguments["value"]}),
                    owner,
                )
            else:
                raise ValueError("Unknown workflow tool")
            connection.execute(
                text(
                    "INSERT INTO sv3.workflow_tool_executions(id,farmer_id,tool_name,argument_hash,result) VALUES(:id,:owner,:name,:hash,CAST(:result AS jsonb))"
                ),
                {
                    "id": key,
                    "owner": owner,
                    "name": name,
                    "hash": digest,
                    "result": json.dumps(result, ensure_ascii=False),
                },
            )
            return result
        finally:
            _tool_connection.reset(token)


@router.get("/weather-brief")
def weather_brief(owner: Owner, farm_key: str = Query("", max_length=120)):
    """Source-backed weather context, not an agronomic prescription."""
    from skyview.assistant.weather_tools import forecast

    data = forecast(owner, days=3, farm_key=farm_key)
    if not data.get("available"):
        return {
            "available": False,
            "signals": [],
            "message": data.get(
                "message", "No fresh linked weather forecast is available"
            ),
            "farm_choices": data.get("farm_choices", []),
            "requires_farm_selection": data.get("requires_farm_selection", False),
        }
    signals = []
    for row in data.get("records", []):
        rain = row.get("rainfall_mm")
        high = row.get("temperature_max_c")
        if rain is not None and float(rain) >= 10:
            signals.append(
                {
                    "date": row["valid_on"],
                    "kind": "rain",
                    "title": "Rain is forecast",
                    "detail": f"Grid forecast: {rain} mm. Review planned outdoor work against actual field conditions.",
                }
            )
        if high is not None and float(high) >= 35:
            signals.append(
                {
                    "date": row["valid_on"],
                    "kind": "heat",
                    "title": "A hot day is forecast",
                    "detail": f"Grid forecast maximum: {high} °C. Review work timing, drinking water and shade.",
                }
            )
    return {
        "available": True,
        "signals": signals[:6],
        "records": data.get("records", []),
        "provenance": data.get("provenance"),
        "note": "Simple weather flags: rain ≥10 mm or maximum temperature ≥35 °C. Regional grid forecasts do not measure this field or prescribe irrigation, spraying or treatment.",
    }
