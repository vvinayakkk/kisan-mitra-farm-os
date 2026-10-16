"""Farmer-entered service records and consented group checklists. No external bookings."""

import hashlib
import secrets
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import DataError

from skyview.api.v3_farm_workflow_routes import connection_scope
from skyview.api.v3_routes import Owner
from skyview.data.v3 import repository

router = APIRouter(prefix="/api/farm-workspace", tags=["Services and shared farm work"])


class Input(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False
    )


class Service(Input):
    title: str = Field(min_length=2, max_length=160)
    service_type: Literal["labour", "machinery", "transport", "expert", "other"]
    supplier: str = Field(default="", max_length=160)
    quote_inr: Decimal | None = Field(
        default=None, ge=0, le=100000000, decimal_places=2, max_digits=14
    )
    scheduled_on: date | None = None
    status: Literal[
        "planned",
        "requested",
        "quote_recorded",
        "farmer_confirmed",
        "farmer_completed",
        "cancelled",
    ] = "planned"
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def confirmed_context(self):
        if (
            self.status in {"quote_recorded", "farmer_confirmed", "farmer_completed"}
            and not self.supplier
        ):
            raise ValueError(
                "Record the supplier you spoke to before confirming service details"
            )
        if self.status == "quote_recorded" and self.quote_inr is None:
            raise ValueError("Record the quoted amount")
        if (
            self.status == "farmer_completed"
            and self.scheduled_on
            and self.scheduled_on > datetime.now(ZoneInfo("Asia/Kolkata")).date()
        ):
            raise ValueError("A completed service cannot be dated in the future")
        return self


class ServiceEdit(Service):
    row_version: int = Field(ge=1)


class GroupInput(Input):
    name: str = Field(min_length=2, max_length=100)


class Invite(Input):
    consent_to_share_group_plans: Literal[True]
    role: Literal["reader", "contributor"]


class Join(Input):
    consent_to_share_display_name: Literal[True]
    code: str = Field(min_length=32, max_length=120)


class SharedTask(Input):
    title: str = Field(min_length=2, max_length=160)
    notes: str = Field(default="", max_length=2000)
    due_on: date | None = None


class SharedTaskEdit(SharedTask):
    completed: bool
    row_version: int = Field(ge=1)


def rows(conn, sql, params=None):
    return [
        repository.clean(dict(row))
        for row in conn.execute(text(sql), params or {}).mappings()
    ]


def one(conn, sql, params):
    result = rows(conn, sql, params)
    if not result:
        raise HTTPException(404, "Record not found")
    return result[0]


def group(conn, gid, write=False, owner_only=False):
    role = conn.execute(text("SELECT sv3.group_role(:id)"), {"id": str(gid)}).scalar()
    if role is None:
        raise HTTPException(404, "Group not found")
    if owner_only and role != "owner" or write and role not in {"owner", "contributor"}:
        raise HTTPException(403, "Your group role cannot change this record")
    return role


@router.get("/service-requests")
def services(owner: Owner):
    with connection_scope(owner) as conn:
        return {
            "items": rows(
                conn,
                "SELECT * FROM sv3.service_requests ORDER BY updated_at DESC LIMIT 200",
            ),
            "note": "Farmer-entered requests and quotes. No supplier was contacted, payment processed or external booking made by this app.",
        }


@router.post("/service-requests")
def create_service(body: Service, owner: Owner):
    with connection_scope(owner, write=True) as conn:
        return one(
            conn,
            "INSERT INTO sv3.service_requests(farmer_id,title,service_type,supplier,quote_inr,scheduled_on,status,notes) VALUES(:owner,:title,:service_type,:supplier,:quote_inr,:scheduled_on,:status,:notes) RETURNING *",
            {**body.model_dump(), "owner": owner},
        )


@router.patch("/service-requests/{sid}")
def edit_service(sid: uuid.UUID, body: ServiceEdit, owner: Owner):
    with connection_scope(owner, write=True) as conn:
        before = one(
            conn,
            "SELECT row_version FROM sv3.service_requests WHERE id=:id FOR UPDATE",
            {"id": str(sid)},
        )
        if before["row_version"] != body.row_version:
            raise HTTPException(
                409, "This service record changed. Refresh before editing."
            )
        return one(
            conn,
            "UPDATE sv3.service_requests SET title=:title,service_type=:service_type,supplier=:supplier,quote_inr=:quote_inr,scheduled_on=:scheduled_on,status=:status,notes=:notes,row_version=row_version+1,updated_at=now() WHERE id=:id RETURNING *",
            {**body.model_dump(), "id": str(sid)},
        )


@router.get("/groups")
def groups(owner: Owner):
    with connection_scope(owner) as conn:
        return {
            "items": rows(
                conn,
                "SELECT id,name,created_at,sv3.group_role(id) role FROM sv3.farm_groups ORDER BY created_at DESC LIMIT 100",
            )
        }


@router.post("/groups")
def create_group(body: GroupInput, owner: Owner):
    with connection_scope(owner, write=True) as conn:
        result = one(
            conn,
            "INSERT INTO sv3.farm_groups(owner_farmer_id,name) VALUES(:owner,:name) RETURNING id,name,created_at",
            {"owner": owner, "name": body.name},
        )
        return {**result, "role": "owner"}


@router.post("/groups/join")
def join_group(body: Join, owner: Owner):
    try:
        with connection_scope(owner, write=True) as conn:
            gid = conn.execute(
                text("SELECT sv3.accept_group_invite(:hash)"),
                {"hash": hashlib.sha256(body.code.encode()).hexdigest()},
            ).scalar()
            return one(
                conn,
                "SELECT id,name,sv3.group_role(id) role FROM sv3.farm_groups WHERE id=:id",
                {"id": str(gid)},
            )
    except DataError as exc:
        raise HTTPException(
            422,
            "This invitation is unavailable, expired, already used, or you already belong to the group.",
        ) from exc


@router.get("/groups/{gid}/members")
def members(gid: uuid.UUID, owner: Owner):
    with connection_scope(owner) as conn:
        group(conn, gid)
        return {
            "items": rows(
                conn,
                "SELECT farmer_id,display_name,role FROM sv3.group_members WHERE group_id=:id ORDER BY created_at",
                {"id": str(gid)},
            )
        }


@router.delete("/groups/{gid}/members/{person}")
def revoke_member(gid: uuid.UUID, person: uuid.UUID, owner: Owner):
    with connection_scope(owner, write=True) as conn:
        group(conn, gid, owner_only=True)
        result = conn.execute(
            text(
                "DELETE FROM sv3.group_members WHERE group_id=:id AND farmer_id=:person"
            ),
            {"id": str(gid), "person": str(person)},
        )
        if not result.rowcount:
            raise HTTPException(404, "Member not found")
    return {"revoked": True}


@router.post("/groups/{gid}/invites")
def create_invite(gid: uuid.UUID, body: Invite, owner: Owner):
    code = secrets.token_urlsafe(32)
    with connection_scope(owner, write=True) as conn:
        group(conn, gid, owner_only=True)
        result = one(
            conn,
            "INSERT INTO sv3.group_invites(group_id,token_hash,role,expires_at) VALUES(:id,:hash,:role,now()+interval '7 days') RETURNING id,role,expires_at",
            {
                "id": str(gid),
                "hash": hashlib.sha256(code.encode()).hexdigest(),
                "role": body.role,
            },
        )
        return {
            **result,
            "code": code,
            "note": "Shown once. Single use within seven days. Shares only this group’s plans and member display names, never private farm records. No message was sent.",
        }


@router.get("/groups/{gid}/invites")
def invites(gid: uuid.UUID, owner: Owner):
    with connection_scope(owner) as conn:
        group(conn, gid, owner_only=True)
        return {
            "items": rows(
                conn,
                "SELECT id,role,expires_at,(used_by IS NOT NULL) used,(revoked_at IS NOT NULL) revoked FROM sv3.group_invites WHERE group_id=:id ORDER BY created_at DESC LIMIT 100",
                {"id": str(gid)},
            )
        }


@router.delete("/groups/{gid}/invites/{iid}")
def revoke_invite(gid: uuid.UUID, iid: uuid.UUID, owner: Owner):
    with connection_scope(owner, write=True) as conn:
        group(conn, gid, owner_only=True)
        result = conn.execute(
            text(
                "UPDATE sv3.group_invites SET revoked_at=now() WHERE group_id=:gid AND id=:id AND used_by IS NULL"
            ),
            {"gid": str(gid), "id": str(iid)},
        )
        if not result.rowcount:
            raise HTTPException(404, "Unused invitation not found")
    return {"revoked": True}


@router.get("/groups/{gid}/tasks")
def tasks(gid: uuid.UUID, owner: Owner):
    with connection_scope(owner) as conn:
        group(conn, gid)
        return {
            "items": rows(
                conn,
                "SELECT * FROM sv3.group_tasks WHERE group_id=:id ORDER BY completed,due_on NULLS LAST,created_at DESC LIMIT 200",
                {"id": str(gid)},
            )
        }


@router.post("/groups/{gid}/tasks")
def create_task(gid: uuid.UUID, body: SharedTask, owner: Owner):
    with connection_scope(owner, write=True) as conn:
        group(conn, gid, write=True)
        return one(
            conn,
            "INSERT INTO sv3.group_tasks(group_id,creator_id,title,notes,due_on) VALUES(:gid,:owner,:title,:notes,:due_on) RETURNING *",
            {**body.model_dump(), "gid": str(gid), "owner": owner},
        )


@router.patch("/groups/{gid}/tasks/{tid}")
def edit_task(gid: uuid.UUID, tid: uuid.UUID, body: SharedTaskEdit, owner: Owner):
    with connection_scope(owner, write=True) as conn:
        group(conn, gid, write=True)
        old = one(
            conn,
            "SELECT row_version FROM sv3.group_tasks WHERE id=:id AND group_id=:gid FOR UPDATE",
            {"id": str(tid), "gid": str(gid)},
        )
        if old["row_version"] != body.row_version:
            raise HTTPException(409, "This group task changed. Refresh before editing.")
        return one(
            conn,
            "UPDATE sv3.group_tasks SET title=:title,notes=:notes,due_on=:due_on,completed=:completed,row_version=row_version+1,updated_at=now() WHERE id=:id AND group_id=:gid RETURNING *",
            {**body.model_dump(), "id": str(tid), "gid": str(gid)},
        )
