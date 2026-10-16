"""Public notices do not expose private farm records; bilateral transitions are real."""

import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from skyview.api.v3_exchange_routes import router
from skyview.assistant import store

BASE = "/api/exchange"


@pytest.fixture
def people(monkeypatch):
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
    app.include_router(router)
    return TestClient(app), headers


def notice(client, header, status="published"):
    payload = {
        "title": "Test shared thresher " + uuid.uuid4().hex[:6],
        "category": "equipment",
        "kind": "offer",
        "quantity": 1,
        "unit": "machine",
        "state": "Maharashtra",
        "district": "Pune",
        "exchange_for": "labour",
        "status": status,
        "consent_to_publish": status == "published",
    }
    response = client.post(BASE + "/listings", headers=header, json=payload)
    assert response.status_code == 200, response.text
    return response.json(), payload


def connect(client, header, item):
    response = client.post(
        BASE + "/conversations",
        headers=header,
        json={"listing_id": item["id"], "consent_to_share_display_name": True},
    )
    assert response.status_code == 200, response.text
    return response.json()


def action(client, header, thread, verb, terms=""):
    payload = {
        "action": verb,
        "row_version": thread["row_version"],
        "client_key": str(uuid.uuid4()),
        "terms": terms,
    }
    response = client.post(
        f"{BASE}/conversations/{thread['id']}/actions", headers=header, json=payload
    )
    return response, payload


def test_consent_drafts_private_and_notice_versions(people):
    client, (owner, other, _) = people
    assert client.get(BASE + "/listings").status_code == 401
    draft, payload = notice(client, owner, "draft")
    assert draft["id"] not in [
        r["id"] for r in client.get(BASE + "/listings", headers=other).json()["items"]
    ]
    assert (
        client.post(
            BASE + "/listings", headers=owner, json={**payload, "status": "published"}
        ).status_code
        == 422
    )
    edit = {
        **payload,
        "row_version": 1,
        "status": "published",
        "consent_to_publish": True,
    }
    assert (
        client.patch(
            BASE + "/listings/" + draft["id"], headers=other, json=edit
        ).status_code
        == 404
    )
    assert (
        client.patch(
            BASE + "/listings/" + draft["id"], headers=owner, json=edit
        ).json()["row_version"]
        == 2
    )
    assert (
        client.patch(
            BASE + "/listings/" + draft["id"], headers=owner, json=edit
        ).status_code
        == 409
    )
    assert (
        client.post(
            BASE + "/conversations",
            headers=owner,
            json={"listing_id": draft["id"], "consent_to_share_display_name": True},
        ).status_code
        == 422
    )


def test_private_messages_cursors_and_idempotency(people):
    client, (owner, other, outsider) = people
    item, _ = notice(client, owner)
    thread = connect(client, other, item)
    assert connect(client, other, item)["id"] == thread["id"]
    url = f"{BASE}/conversations/{thread['id']}"
    assert client.get(url, headers=outsider).status_code == 404
    payload = {"text": "Can we meet after harvest?", "client_key": str(uuid.uuid4())}
    msg = client.post(url + "/messages", headers=other, json=payload)
    assert msg.status_code == 200, msg.text
    assert (
        client.post(url + "/messages", headers=other, json=payload).json()["sequence"]
        == msg.json()["sequence"]
    )
    assert (
        client.post(
            url + "/messages", headers=other, json={**payload, "text": "Changed words"}
        ).status_code
        == 409
    )
    assert (
        client.post(url + "/messages", headers=outsider, json=payload).status_code
        == 404
    )
    assert (
        client.get(url + "/messages", headers=owner).json()["items"][0]["text"]
        == payload["text"]
    )
    assert (
        client.get(
            url + "/messages?after=" + str(msg.json()["sequence"]), headers=owner
        ).json()["items"]
        == []
    )
    assert client.get(url, headers=outsider).status_code == 404


def test_real_bilateral_agreement_handover_completion_and_replay(people):
    client, (owner, other, outsider) = people
    item, _ = notice(client, owner)
    thread = connect(client, other, item)
    assert action(client, other, thread, "complete")[0].status_code == 409
    proposed, payload = action(
        client,
        owner,
        thread,
        "propose",
        "One machine for two days of harvest labour; pickup Friday",
    )
    assert proposed.status_code == 200, proposed.text
    proposed = proposed.json()
    assert action(client, owner, proposed, "accept")[0].status_code == 409
    assert action(client, other, thread, "accept")[0].status_code == 409
    rival = connect(client, outsider, item)
    rival = action(client, outsider, rival, "propose", "Competing request")[0].json()
    accepted, _ = action(client, other, proposed, "accept")
    assert accepted.status_code == 200, accepted.text
    current = accepted.json()
    assert current["status"] == "agreed"
    assert action(client, owner, rival, "accept")[0].status_code == 409
    first = action(client, owner, current, "handover")[0]
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "agreed"
    current = action(client, other, first.json(), "handover")[0].json()
    assert current["status"] == "handover"
    current = action(client, owner, current, "complete")[0].json()
    assert current["status"] == "handover"
    current = action(client, other, current, "complete")[0].json()
    assert current["status"] == "completed"
    replay = client.post(
        f"{BASE}/conversations/{thread['id']}/actions", headers=owner, json=payload
    )
    assert replay.json() == proposed
    assert (
        client.post(
            f"{BASE}/conversations/{thread['id']}/messages",
            headers=owner,
            json={"text": "Late message", "client_key": str(uuid.uuid4())},
        ).status_code
        == 409
    )
    detail = client.get(f"{BASE}/conversations/{thread['id']}", headers=other).json()
    assert len(detail["timeline"]) == 6
    assert detail["thread"]["status"] == "completed"


def test_withdrawn_listing_blocks_acceptance_and_matches_explain_fit(people):
    client, (owner, other, _) = people
    item, payload = notice(client, owner)
    own, own_payload = notice(client, other)
    own_payload.update(kind="request", exchange_for="", row_version=1)
    client.patch(BASE + "/listings/" + own["id"], headers=other, json=own_payload)
    match = client.get(BASE + "/matches?listing_id=" + own["id"], headers=other)
    assert match.status_code == 200, match.text
    candidate = next(r for r in match.json()["items"] if r["id"] == item["id"])
    assert candidate["match_score"] >= 70 and candidate["distance_km"] is None
    assert (
        client.get(BASE + "/matches?listing_id=" + own["id"], headers=owner).status_code
        == 404
    )
    thread = connect(client, other, item)
    thread = action(client, owner, thread, "propose", "One machine for harvest labour")[
        0
    ].json()
    assert (
        client.patch(
            BASE + "/listings/" + item["id"],
            headers=owner,
            json={**payload, "status": "withdrawn", "row_version": 1},
        ).status_code
        == 200
    )
    assert action(client, other, thread, "accept")[0].status_code == 409
    cancelled = action(client, other, thread, "cancel")[0]
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"


def test_named_resources_are_not_matched_only_by_category(people):
    client, (owner, other, _) = people
    wrong, _ = notice(client, owner)
    right, right_payload = notice(client, owner)
    client.patch(
        BASE + "/listings/" + right["id"],
        headers=owner,
        json={**right_payload, "title": "Tractor with cultivator", "row_version": 1},
    )
    request, payload = notice(client, other)
    client.patch(
        BASE + "/listings/" + request["id"],
        headers=other,
        json={
            **payload,
            "title": "Need tractor",
            "kind": "request",
            "exchange_for": "",
            "row_version": 1,
        },
    )
    matches = client.get(
        BASE + "/matches?listing_id=" + request["id"], headers=other
    ).json()["items"]
    assert right["id"] in [r["id"] for r in matches]
    assert wrong["id"] not in [r["id"] for r in matches]


def test_disputed_resource_remains_reserved_and_agreed_cannot_cancel(people):
    client, (owner, other, outsider) = people
    item, _ = notice(client, owner)
    thread = connect(client, other, item)
    competing = connect(client, outsider, item)
    competing = action(client, outsider, competing, "propose", "Competing terms")[
        0
    ].json()
    thread = action(
        client, owner, thread, "propose", "One whole machine for two work days"
    )[0].json()
    thread = action(client, other, thread, "accept")[0].json()
    assert action(client, owner, thread, "cancel")[0].status_code == 409
    disputed = action(
        client, other, thread, "dispute", "Handover did not happen as agreed"
    )[0]
    assert disputed.status_code == 200 and disputed.json()["status"] == "disputed"
    assert action(client, owner, competing, "accept")[0].status_code == 409
    discovery = client.get(BASE + "/listings", headers=outsider).json()["items"]
    assert item["id"] not in [r["id"] for r in discovery]
    timeline = client.get(f"{BASE}/conversations/{thread['id']}", headers=owner).json()[
        "timeline"
    ]
    assert timeline[-1]["result"]["action_note"] == "Handover did not happen as agreed"


def test_matching_does_not_reoffer_an_agreed_whole_notice(people):
    client, (owner, other, _) = people
    item, _ = notice(client, owner)
    thread = connect(client, other, item)
    proposed, _ = action(
        client, owner, thread, "propose", "One thresher for one day of labour"
    )
    assert proposed.status_code == 200
    accepted, _ = action(client, other, proposed.json(), "accept")
    assert accepted.status_code == 200
    matches = client.get(
        BASE + "/matches", headers=owner, params={"listing_id": item["id"]}
    )
    assert matches.status_code == 200
    assert matches.json()["items"] == []
    assert "committed" in matches.json()["note"]
