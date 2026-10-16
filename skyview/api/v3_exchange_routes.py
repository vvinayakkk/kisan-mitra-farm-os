"""Consented resource discovery and private, durable bilateral exchange coordination."""

import hashlib
import json
import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field, field_validator, model_validator
from sqlalchemy import text

from skyview.api.v3_farm_workflow_routes import Input, connection_scope
from skyview.api.v3_routes import Owner
from skyview.api.v3_shared_work_routes import one, rows
from skyview.data.v3 import db

router = APIRouter(prefix="/api/exchange", tags=["Farmer exchange"])
Category = Literal["equipment", "labour", "transport", "produce"]


class Listing(Input):
    title: str = Field(min_length=2, max_length=160)
    category: Category
    kind: Literal["offer", "request"]
    description: str = Field(default="", max_length=2000)
    quantity: Decimal = Field(gt=0, le=10000000, decimal_places=3)
    unit: str = Field(min_length=1, max_length=40)
    state: str = Field(min_length=2, max_length=100)
    district: str = Field(min_length=2, max_length=100)
    available_on: date | None = None
    exchange_for: str = Field(default="", max_length=500)
    status: Literal["draft", "published", "withdrawn"] = "draft"
    consent_to_publish: bool = False

    @field_validator("consent_to_publish", mode="before")
    @classmethod
    def literal_consent(cls, value):
        if type(value) is not bool:
            raise ValueError("Consent must be an explicit boolean")
        return value

    @model_validator(mode="after")
    def consent(self):
        if self.status == "published" and not self.consent_to_publish:
            raise ValueError(
                "Publishing requires consent to share this notice and your display name"
            )
        return self


class ListingEdit(Listing):
    row_version: int = Field(ge=1)


class Connect(Input):
    listing_id: uuid.UUID
    consent_to_share_display_name: Literal[True]

    @field_validator("consent_to_share_display_name", mode="before")
    @classmethod
    def literal_consent(cls, value):
        if value is not True:
            raise ValueError("Explicit display-name sharing consent required")
        return value


class Message(Input):
    text: str = Field(min_length=1, max_length=4000)
    client_key: uuid.UUID


class Action(Input):
    action: Literal["propose", "accept", "handover", "complete", "cancel", "dispute"]
    row_version: int = Field(ge=1)
    client_key: uuid.UUID
    terms: str = Field(default="", max_length=4000)


def present(thread, owner):
    return {
        **thread,
        "my_farmer_id": str(owner),
        "can_accept": thread["status"] == "negotiating"
        and bool(thread["proposal"])
        and thread["proposal"]["proposer_id"] != str(owner),
        "my_role": "owner" if str(thread["owner_id"]) == str(owner) else "requester",
        "participants": [
            {"farmer_id": thread["owner_id"], "display_name": thread["owner_name"]},
            {
                "farmer_id": thread["requester_id"],
                "display_name": thread["requester_name"],
            },
        ],
    }


def thread_row(conn, cid, lock=False):
    return one(
        conn,
        "SELECT * FROM sv3.exchange_conversations WHERE id=:id"
        + (" FOR UPDATE" if lock else ""),
        {"id": str(cid)},
    )


@router.get("/listings")
def listings(
    owner: Owner,
    category: Category | None = None,
    kind: Literal["offer", "request"] | None = None,
    state: str = "",
    district: str = "",
    q: str = Query(default="", max_length=160),
    mine: bool = False,
    listing_id: uuid.UUID | None = None,
):
    with connection_scope(owner) as conn:
        filters = [
            "farmer_id=:owner"
            if mine
            else "status='published' AND farmer_id<>:owner AND sv3.exchange_listing_open(id)"
        ]
        params = {"owner": owner}
        if listing_id:
            filters.append("id=:listing_id")
            params["listing_id"] = str(listing_id)
        for field, value in [
            ("category", category),
            ("kind", kind),
            ("state", state),
            ("district", district),
        ]:
            if value:
                filters.append(f"lower({field})=lower(:{field})")
                params[field] = value
        if q:
            filters.append(
                "(title ILIKE :q OR description ILIKE :q OR exchange_for ILIKE :q)"
            )
            params["q"] = "%" + q.replace("%", "\\%").replace("_", "\\_") + "%"
        result = rows(
            conn,
            "SELECT *,sv3.exchange_listing_open(id) AS available_for_new_exchange FROM sv3.exchange_listings WHERE "
            + " AND ".join(filters)
            + " ORDER BY CASE WHEN kind='offer' THEN 0 ELSE 1 END, updated_at DESC,id LIMIT 100",
            params,
        )
        for notice in result:
            notice["data_origin"] = (
                "synthetic"
                if notice["description"].startswith(
                    ("Fictional demo notice.", "Sample resource listing.")
                )
                and db.mode() == "v3_demo"
                else "farmer_entered"
            )
            notice["source"] = (
                "Sample sharing catalogue"
                if notice["data_origin"] == "synthetic"
                else "Farmer-entered notice"
            )
        return {
            "items": result,
            "data_mode": db.mode(),
            "origin": "mixed"
            if any(item["data_origin"] == "synthetic" for item in result)
            else "farmer_entered",
            "location_precision": "district",
            "distance_km": None,
        }


@router.post("/listings")
def create_listing(body: Listing, owner: Owner):
    with connection_scope(owner, write=True) as conn:
        name = one(
            conn,
            "SELECT display_name FROM sv3.farmers WHERE id=:owner AND status IN ('active','demo')",
            {"owner": owner},
        )["display_name"]
        params = {
            **body.model_dump(exclude={"consent_to_publish"}),
            "owner": owner,
            "name": name,
        }
        return one(
            conn,
            "INSERT INTO sv3.exchange_listings(farmer_id,display_name,title,category,kind,description,quantity,unit,state,district,available_on,exchange_for,status) VALUES(:owner,:name,:title,:category,:kind,:description,:quantity,:unit,:state,:district,:available_on,:exchange_for,:status) RETURNING *",
            params,
        )


@router.patch("/listings/{lid}")
def edit_listing(lid: uuid.UUID, body: ListingEdit, owner: Owner):
    with connection_scope(owner, write=True) as conn:
        conn.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:id AS text),0))"),
            {"id": str(lid)},
        )
        current = one(
            conn,
            "SELECT * FROM sv3.exchange_listings WHERE id=:id AND farmer_id=:owner FOR UPDATE",
            {"id": str(lid), "owner": owner},
        )
        if current["row_version"] != body.row_version:
            raise HTTPException(409, "Notice changed; refresh before editing")
        return one(
            conn,
            "UPDATE sv3.exchange_listings SET title=:title,category=:category,kind=:kind,description=:description,quantity=:quantity,unit=:unit,state=:state,district=:district,available_on=:available_on,exchange_for=:exchange_for,status=:status,row_version=row_version+1,updated_at=now() WHERE id=:id RETURNING *",
            {
                **body.model_dump(exclude={"consent_to_publish", "row_version"}),
                "id": str(lid),
            },
        )


def resource_words(value):
    stop = {
        "a",
        "an",
        "the",
        "for",
        "and",
        "of",
        "need",
        "offer",
        "request",
        "test",
        "shared",
        "fixture",
        "available",
        "wanted",
        "machine",
    }
    words = set(re.findall(r"[a-z]+", value.lower())) - stop
    return {
        word[:-1] if word.endswith("s") and len(word) > 3 else word for word in words
    }


@router.get("/matches")
def matches(listing_id: uuid.UUID, owner: Owner):
    with connection_scope(owner) as conn:
        source = one(
            conn,
            "SELECT * FROM sv3.exchange_listings WHERE id=:id AND farmer_id=:owner",
            {"id": str(listing_id), "owner": owner},
        )
        reserved = conn.execute(
            text(
                "SELECT EXISTS(SELECT 1 FROM sv3.exchange_conversations WHERE listing_id=:id AND status IN ('agreed','handover','completed','disputed'))"
            ),
            {"id": str(listing_id)},
        ).scalar()
        if source["status"] != "published" or reserved:
            return {
                "items": [],
                "distance_km": None,
                "note": "Publish an available notice before finding matches. This notice is withdrawn, a draft or already committed.",
            }
        candidates = rows(
            conn,
            "SELECT * FROM sv3.exchange_listings WHERE status='published' AND farmer_id<>:owner AND sv3.exchange_listing_open(id) ORDER BY updated_at DESC LIMIT 500",
            {"owner": owner},
        )
        result = []
        wanted = resource_words(source["exchange_for"])
        source_words = resource_words(source["title"])
        for candidate in candidates:
            reasons = []
            score = 0
            candidate_words = resource_words(candidate["title"])
            same_resource = (
                candidate["category"] == source["category"]
                and candidate["kind"] != source["kind"]
                and bool(source_words & candidate_words)
            )
            wanted_fit = (
                source["kind"] == "offer"
                and candidate["kind"] == "offer"
                and bool(wanted & (candidate_words | {candidate["category"]}))
            )
            return_fit = bool(
                resource_words(candidate["exchange_for"])
                & (source_words | {source["category"]})
            )
            if not same_resource and not wanted_fit:
                continue
            if same_resource:
                score += 40
                reasons.append(
                    "Named resource matches with complementary offer/request"
                )
            if wanted_fit:
                score += 30
                reasons.append("Resource words match what you want in exchange")
                if return_fit:
                    score += 20
                    reasons.append("Both farmers' stated exchange wishes match")
            if candidate["state"].lower() == source["state"].lower():
                score += 10
                reasons.append("Same state")
                if candidate["district"].lower() == source["district"].lower():
                    score += 20
                    reasons.append("Same district; confirm pickup location privately")
            if (
                candidate["available_on"]
                and candidate["available_on"] == source["available_on"]
            ):
                score += 10
                reasons.append("Same stated availability day")
            result.append(
                {
                    **candidate,
                    "match_score": score,
                    "match_reasons": reasons,
                    "distance_km": None,
                }
            )
        return {
            "items": sorted(result, key=lambda x: -x["match_score"])[:50],
            "note": "Transparent resource and district fit, not a road route or guaranteed availability.",
        }


@router.get("/conversations")
def conversations(owner: Owner):
    with connection_scope(owner) as conn:
        return {
            "items": [
                present(t, owner)
                for t in rows(
                    conn,
                    "SELECT * FROM sv3.exchange_conversations ORDER BY updated_at DESC LIMIT 100",
                )
            ]
        }


@router.post("/conversations")
def connect(body: Connect, owner: Owner):
    with connection_scope(owner, write=True) as conn:
        notice = one(
            conn,
            "SELECT * FROM sv3.exchange_listings WHERE id=:id AND status='published'",
            {"id": str(body.listing_id)},
        )
        existing = rows(
            conn,
            "SELECT * FROM sv3.exchange_conversations WHERE listing_id=:id AND requester_id=:owner",
            {"id": notice["id"], "owner": owner},
        )
        if existing:
            return present(existing[0], owner)
        if not conn.execute(
            text("SELECT sv3.exchange_listing_open(:id)"), {"id": notice["id"]}
        ).scalar():
            raise HTTPException(409, "This notice is already committed to an exchange")
        if str(notice["farmer_id"]) == str(owner):
            raise HTTPException(422, "Choose another farmer's notice")
        pending_count = conn.execute(
            text(
                "SELECT count(*) FROM sv3.exchange_conversations WHERE requester_id=:owner AND status IN ('open','negotiating')"
            ),
            {"owner": owner},
        ).scalar()
        if pending_count >= 200:
            raise HTTPException(
                429, "Close an old request before starting another conversation"
            )
        name = one(
            conn,
            "SELECT display_name FROM sv3.farmers WHERE id=:owner AND status IN ('active','demo')",
            {"owner": owner},
        )["display_name"]

        thread = one(
            conn,
            "INSERT INTO sv3.exchange_conversations(listing_id,listing_title,owner_id,requester_id,owner_name,requester_name) VALUES(:listing,:title,:person,:owner,:name,:mine) ON CONFLICT(listing_id,requester_id) DO UPDATE SET listing_title=exchange_conversations.listing_title RETURNING *",
            {
                "listing": notice["id"],
                "title": notice["title"],
                "person": notice["farmer_id"],
                "owner": owner,
                "name": notice["display_name"],
                "mine": name,
            },
        )
        return present(thread, owner)


@router.get("/conversations/{cid}/messages")
def messages(cid: uuid.UUID, owner: Owner, after: int = Query(default=0, ge=0)):
    with connection_scope(owner) as conn:
        thread_row(conn, cid)
        items = rows(
            conn,
            "SELECT * FROM sv3.exchange_messages WHERE conversation_id=:id AND sequence>:after ORDER BY sequence LIMIT 100",
            {"id": str(cid), "after": after},
        )
        return {
            "items": items,
            "next_cursor": items[-1]["sequence"] if items else after,
        }


@router.get("/conversations/{cid}")
def conversation(cid: uuid.UUID, owner: Owner, include_messages: bool = True):
    with connection_scope(owner) as conn:
        thread = thread_row(conn, cid)
        return {
            "thread": present(thread, owner),
            "messages": rows(
                conn,
                "SELECT * FROM (SELECT * FROM sv3.exchange_messages WHERE conversation_id=:id ORDER BY sequence DESC LIMIT 100) recent ORDER BY sequence",
                {"id": str(cid)},
            )
            if include_messages
            else [],
            "timeline": rows(
                conn,
                "SELECT sequence,actor_id,action,result,created_at FROM (SELECT * FROM sv3.exchange_events WHERE conversation_id=:id ORDER BY sequence DESC LIMIT 200) recent ORDER BY sequence",
                {"id": str(cid)},
            ),
        }


@router.post("/conversations/{cid}/messages")
def send_message(cid: uuid.UUID, body: Message, owner: Owner):
    with connection_scope(owner, write=True) as conn:
        thread = thread_row(conn, cid, lock=True)
        previous = rows(
            conn,
            "SELECT * FROM sv3.exchange_messages WHERE conversation_id=:id AND sender_id=:owner AND client_key=:key",
            {"id": str(cid), "owner": owner, "key": str(body.client_key)},
        )
        if previous:
            if previous[0]["text"] != body.text:
                raise HTTPException(409, "Message key already used for different words")
            return previous[0]
        if thread["status"] in {"cancelled", "completed"}:
            raise HTTPException(409, "This exchange is closed")
        recent_count = conn.execute(
            text(
                "SELECT count(*) FROM sv3.exchange_messages WHERE sender_id=:owner AND created_at>now()-interval '1 minute'"
            ),
            {"owner": owner},
        ).scalar()
        if recent_count >= 60:
            raise HTTPException(
                429, "Please wait a minute before sending more messages"
            )
        message = one(
            conn,
            "INSERT INTO sv3.exchange_messages(conversation_id,sender_id,text,client_key) VALUES(:id,:owner,:text,:key) RETURNING *",
            {
                "id": str(cid),
                "owner": owner,
                "text": body.text,
                "key": str(body.client_key),
            },
        )
        conn.execute(
            text("UPDATE sv3.exchange_conversations SET updated_at=now() WHERE id=:id"),
            {"id": str(cid)},
        )
        return message


@router.post("/conversations/{cid}/actions")
def act(cid: uuid.UUID, body: Action, owner: Owner):
    digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    with connection_scope(owner, write=True) as conn:
        thread = thread_row(conn, cid, lock=True)
        prior = rows(
            conn,
            "SELECT request_hash,result FROM sv3.exchange_events WHERE conversation_id=:id AND actor_id=:owner AND client_key=:key",
            {"id": str(cid), "owner": owner, "key": str(body.client_key)},
        )
        if prior:
            if prior[0]["request_hash"] != digest:
                raise HTTPException(
                    409, "Action key already used for different details"
                )
            return prior[0]["result"]
        if thread["row_version"] != body.row_version:
            raise HTTPException(409, "Exchange changed; refresh before continuing")
        status = thread["status"]
        if status in {"completed", "cancelled", "disputed"}:
            raise HTTPException(409, "This exchange is closed or disputed")
        person = str(owner)
        proposal = thread["proposal"]
        handovers = thread["handovers"]
        completions = thread["completions"]
        if body.action == "propose":
            if status not in {"open", "negotiating"} or len(body.terms.strip()) < 2:
                raise HTTPException(422, "Write terms before both farmers agree")
            proposal = {"terms": body.terms, "proposer_id": person}
            status = "negotiating"
        elif body.action == "accept":
            if (
                status != "negotiating"
                or not proposal
                or proposal["proposer_id"] == person
            ):
                raise HTTPException(
                    409, "Only the other farmer can accept the current proposal"
                )
            if not conn.execute(
                text("SELECT sv3.exchange_available(:id)"), {"id": thread["listing_id"]}
            ).scalar():
                raise HTTPException(
                    409,
                    "This notice was withdrawn or is already committed to another exchange",
                )
            status = "agreed"
        elif body.action == "handover":
            if status != "agreed" or person in handovers:
                raise HTTPException(
                    409, "Agree terms first; each farmer confirms handover once"
                )
            handovers = [*handovers, person]
            if len(handovers) == 2:
                status = "handover"
        elif body.action == "complete":
            if status != "handover" or person in completions:
                raise HTTPException(
                    409, "Both farmers must confirm handover before completion"
                )
            completions = [*completions, person]
            if len(completions) == 2:
                status = "completed"
        elif body.action == "dispute":
            if status not in {"agreed", "handover"} or len(body.terms.strip()) < 2:
                raise HTTPException(422, "Describe the issue on an agreed exchange")
            status = "disputed"
        else:
            if status not in {"open", "negotiating"}:
                raise HTTPException(
                    409,
                    "An agreed exchange requires an issue report instead of unilateral cancellation",
                )
            status = "cancelled"
        updated = one(
            conn,
            "UPDATE sv3.exchange_conversations SET status=:status,proposal=CAST(:proposal AS jsonb),handovers=CAST(:handovers AS jsonb),completions=CAST(:completions AS jsonb),row_version=row_version+1,updated_at=now() WHERE id=:id RETURNING *",
            {
                "id": str(cid),
                "status": status,
                "proposal": json.dumps(proposal),
                "handovers": json.dumps(handovers),
                "completions": json.dumps(completions),
            },
        )
        result = {**present(updated, owner), "action_note": body.terms}
        conn.execute(
            text(
                "INSERT INTO sv3.exchange_events(conversation_id,actor_id,action,client_key,request_hash,result) VALUES(:id,:owner,:action,:key,:hash,CAST(:result AS jsonb))"
            ),
            {
                "id": str(cid),
                "owner": owner,
                "action": body.action,
                "key": str(body.client_key),
                "hash": digest,
                "result": json.dumps(result),
            },
        )
        return result
