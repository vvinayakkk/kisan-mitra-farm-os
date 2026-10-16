"""AI prepares reviewed drafts, never performs an exchange mutation."""

import json
import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from skyview.api import v3_exchange_ai_routes as ai
from skyview.api.v3_exchange_routes import router as exchange_router
from skyview.api.v3_routes import identity
from skyview.assistant import store


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(ai.router)
    app.dependency_overrides[identity] = lambda: "owner"
    monkeypatch.setattr(ai, "identity", lambda *args: "owner")
    monkeypatch.setattr(
        ai,
        "grounded_context",
        lambda *args: {
            "profile": {"state": "Maharashtra", "district": "Pune"},
            "listing": None,
            "data_mode": "v3_demo",
        },
    )
    return TestClient(app)


def fake_reply(monkeypatch, payload, tools=False):
    async def stream(client, messages, tool_list):
        assert tool_list == []
        assert "untrusted" in messages[0]["content"]
        yield {
            "type": "turn",
            "message": {
                "content": json.dumps(payload),
                **({"tool_calls": [{"id": "bad"}]} if tools else {}),
            },
        }

    monkeypatch.setattr(ai.provider, "stream_turn", stream)


def test_partial_listing_is_reviewed_and_uninvented(client, monkeypatch):
    fake_reply(
        monkeypatch,
        {
            "answer": "What quantity can you share?",
            "fields": {
                "title": "Shared thresher",
                "category": "equipment",
                "kind": "offer",
                "quantity": 12,
                "unit": "machine",
                "state": "Maharashtra",
                "district": "Mumbai",
                "description": "Costs 500 rupees",
                "available_on": "2026-10-30",
            },
        },
    )
    response = client.post(
        "/api/exchange/assist",
        json={"intent": "prepare_listing", "message": "I can share my thresher"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["draft"]["fields"]["state"] == "Maharashtra"
    assert set(result["draft"]["fields"]) == {
        "title",
        "category",
        "kind",
        "unit",
        "state",
    }
    assert result["saved"] is False and result["tools_executed"] is False
    assert result["requires_review"] is True and result["questions"]


def test_explicit_quantity_kept(client, monkeypatch):
    fake_reply(
        monkeypatch,
        {
            "answer": "Review your notice.",
            "fields": {"title": "Thresher share", "quantity": 2},
        },
    )
    result = client.post(
        "/api/exchange/assist",
        json={"intent": "prepare_listing", "message": "Offer 2 threshers"},
    ).json()
    assert float(result["draft"]["fields"]["quantity"]) == 2


@pytest.mark.parametrize(
    "payload,tools,code",
    [
        ({"answer": "Done", "fields": {"status": "published"}}, False, 502),
        ({"answer": "Done"}, True, 503),
        ({"answer": "Done", "fields": {"quantity": -2}}, False, 502),
    ],
)
def test_invalid_or_executable_response_rejected(
    client, monkeypatch, payload, tools, code
):
    fake_reply(monkeypatch, payload, tools)
    assert (
        client.post(
            "/api/exchange/assist",
            json={"intent": "prepare_listing", "message": "Help"},
        ).status_code
        == code
    )


def test_provider_unavailable_keeps_exchange_unchanged(client, monkeypatch):
    async def unavailable(*args):
        raise ai.provider.ProviderUnavailable("secret provider body")
        yield

    monkeypatch.setattr(ai.provider, "stream_turn", unavailable)
    response = client.post(
        "/api/exchange/assist", json={"intent": "prepare_listing", "message": "Help"}
    )
    assert response.status_code == 503 and "secret" not in response.text


def test_bad_input_never_calls_ai(client, monkeypatch):
    async def forbidden(*args):
        pytest.fail("Provider must not run")
        yield

    monkeypatch.setattr(ai.provider, "stream_turn", forbidden)
    for payload in [
        {"intent": "publish", "message": "Help"},
        {"intent": "prepare_listing", "message": " "},
        {"intent": "prepare_listing", "message": "x" * 4001},
        {"intent": "prepare_listing", "message": "Help", "listing_id": "not-a-uuid"},
    ]:
        assert client.post("/api/exchange/assist", json=payload).status_code == 422


def test_capability_rechecked(client, monkeypatch):
    fake_reply(monkeypatch, {"answer": "Review this."})
    monkeypatch.setattr(ai, "identity", lambda *args: "another-owner")
    assert (
        client.post(
            "/api/exchange/assist",
            json={"intent": "prepare_listing", "message": "Help"},
        ).status_code
        == 401
    )


def test_private_context_isolated(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Isolated PostgreSQL integration opt-in required")
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    headers = []
    for key in ["DEMO-F0091", "DEMO-F0092", "DEMO-F0093"]:
        monkeypatch.setenv("V3_DEMO_FARMER_KEY", key)
        session = store.create_session()
        headers.append(
            {
                "Authorization": "Bearer " + session["token"],
                "X-Assistant-Session": session["id"],
            }
        )
    app = FastAPI()
    app.include_router(exchange_router)
    app.include_router(ai.router)
    client = TestClient(app)
    owner, other, third = headers
    item = client.post(
        "/api/exchange/listings",
        headers=owner,
        json={
            "title": "AI fixture " + uuid.uuid4().hex[:6],
            "category": "equipment",
            "kind": "offer",
            "quantity": 1,
            "unit": "machine",
            "state": "Maharashtra",
            "district": "Pune",
            "status": "published",
            "consent_to_publish": True,
        },
    ).json()
    thread = client.post(
        "/api/exchange/conversations",
        headers=other,
        json={"listing_id": item["id"], "consent_to_share_display_name": True},
    ).json()
    fake_reply(
        monkeypatch,
        {
            "answer": "Inspect before agreeing.",
            "terms": "Inspect the machine before confirming.",
        },
    )
    assert (
        client.post(
            "/api/exchange/assist",
            headers=third,
            json={
                "intent": "review_exchange",
                "message": "Review",
                "conversation_id": thread["id"],
            },
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/exchange/assist",
            headers=other,
            json={
                "intent": "compare_matches",
                "message": "Compare",
                "listing_id": item["id"],
            },
        ).status_code
        == 404
    )
    before = client.get(
        "/api/exchange/conversations/" + thread["id"], headers=owner
    ).json()
    response = client.post(
        "/api/exchange/assist",
        headers=other,
        json={
            "intent": "draft_terms",
            "message": "Draft terms",
            "conversation_id": thread["id"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["draft"]["kind"] == "terms"
    assert (
        client.get("/api/exchange/conversations/" + thread["id"], headers=owner).json()
        == before
    )
    assert (
        client.post(
            "/api/exchange/assist",
            json={"intent": "prepare_listing", "message": "Help"},
        ).status_code
        == 401
    )


def test_metadata_and_quantity_cannot_justify_money():
    body = ai.Assist(intent="prepare_listing", message="Share 1 machine")
    reply = ai.ModelReply(
        answer="Review.",
        fields={"title": "Machine share", "description": "Price INR 1; deposit 500"},
    )
    context = {
        "profile": {},
        "listing": {
            "id": "abc-500",
            "quantity": 1,
            "row_version": 500,
            "updated_at": "2026-10-13",
        },
        "matches": {"items": [{"match_score": 500}]},
    }
    result = ai.reviewed_draft(reply, body, context)
    assert "description" not in result["fields"]
    assert "500" not in ai.prose_evidence(context)
    terms = ai.ModelReply(answer="Review.", terms="Pay INR 1 for the machine.")
    assert (
        ai.reviewed_draft(
            terms, ai.Assist(intent="draft_terms", message="Share 1 machine"), context
        )
        is None
    )


def test_agreed_thread_cannot_get_new_terms(monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def scoped(*args, **kwargs):
        yield object()

    monkeypatch.setattr(ai, "connection_scope", scoped)
    monkeypatch.setattr(ai, "one", lambda *args: {"state": "Maharashtra"})
    monkeypatch.setattr(ai.db, "mode", lambda: "v3_demo")
    monkeypatch.setattr(
        ai,
        "conversation",
        lambda *args: {
            "thread": {"owner_id": "owner", "requester_id": "other", "status": "agreed"}
        },
    )
    with pytest.raises(ai.HTTPException) as failure:
        ai.grounded_context(
            ai.Assist(
                intent="draft_terms",
                message="Change terms",
                conversation_id=uuid.uuid4(),
            ),
            "owner",
        )
    assert failure.value.status_code == 409


def test_provider_context_is_bounded_and_minimal():
    listing = ai.listing_context(
        {
            "id": "listing",
            "title": "Thresher",
            "farmer_id": "private",
            "description": "d" * 2000,
            "exchange_for": "e" * 900,
            "row_version": 123,
            "created_at": "timestamp",
        }
    )
    assert len(listing["description"]) == 600 and len(listing["exchange_for"]) == 600
    assert (
        "farmer_id" not in listing
        and "created_at" not in listing
        and "row_version" not in listing
    )
    context = ai.conversation_context(
        {
            "thread": {
                "owner_id": "owner",
                "requester_id": "other",
                "status": "open",
                "client_secret": "never",
                "proposal": {"terms": "t" * 4000, "proposer_id": "other"},
            },
            "messages": [
                {"id": str(i), "sender_id": "owner", "text": str(i) + "x" * 4000}
                for i in range(30)
            ],
            "timeline": [
                {
                    "actor_id": "other",
                    "action": "propose",
                    "result": {
                        "status": "negotiating",
                        "action_note": "n" * 4000,
                        "private_metadata": "never",
                    },
                }
                for i in range(30)
            ],
        },
        "owner",
    )
    assert sum(len(message["text"]) for message in context["messages"]) <= 12000
    assert all(len(message["text"]) <= 1200 for message in context["messages"])
    assert context["messages"][-1]["text"].startswith("29")
    assert len(context["timeline"]) == 20 and all(
        len(event["note"]) == 300 for event in context["timeline"]
    )
    assert "never" not in json.dumps(context)
    assert "owner_id" not in context["thread"]


def test_provider_enum_case_and_resource_kind_are_reviewable():
    reply = ai.parse_reply(
        json.dumps(
            {
                "answer": "Review this notice.",
                "fields": {
                    "category": "Equipment",
                    "kind": "Sprayer",
                    "quantity": "1",
                    "unit": "piece",
                },
            }
        )
    )
    assert reply.fields.category == "equipment"
    assert reply.fields.kind is None
    assert "offering" in reply.questions[0]
    assert ai.reviewed_draft(
        reply,
        ai.Assist(intent="prepare_listing", message="Sprayer for 2 days"),
        {"profile": {}, "listing": None},
    )["fields"] == {"category": "equipment", "unit": "piece"}
