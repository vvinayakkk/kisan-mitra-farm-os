"""Independent exchange regressions: disclosure, isolation and replay semantics."""

import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from skyview.api.v3_exchange_routes import router
from skyview.assistant import store


@pytest.fixture
def exchange_accounts(monkeypatch):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Dedicated PostgreSQL test database required")
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    headers = []
    for key in ["DEMO-F0095", "DEMO-F0096", "DEMO-F0097"]:
        monkeypatch.setenv("V3_DEMO_FARMER_KEY", key)
        account = store.create_session()
        headers.append(
            {
                "Authorization": "Bearer " + account["token"],
                "X-Assistant-Session": account["id"],
            }
        )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), headers


def notice():
    return {
        "title": "Security fixture " + str(uuid.uuid4()),
        "category": "equipment",
        "kind": "offer",
        "quantity": "1",
        "unit": "machine",
        "state": "Maharashtra",
        "district": "Test district",
        "status": "published",
        "consent_to_publish": True,
    }


def setup_thread(client, headers):
    owner, requester, _ = headers
    listing = client.post("/api/exchange/listings", json=notice(), headers=owner).json()
    response = client.post(
        "/api/exchange/conversations",
        json={"listing_id": listing["id"], "consent_to_share_display_name": True},
        headers=requester,
    )
    assert response.status_code == 200, response.text
    return listing, response.json()


def test_unauthenticated_and_foreign_participants_cannot_read_or_write(
    exchange_accounts,
):
    client, headers = exchange_accounts
    _, thread = setup_thread(client, headers)
    base = "/api/exchange/conversations/" + thread["id"]
    assert client.get("/api/exchange/listings").status_code == 401
    assert client.get(base, headers=headers[2]).status_code == 404
    assert client.get(base + "/messages", headers=headers[2]).status_code == 404
    assert (
        client.post(
            base + "/messages",
            headers=headers[2],
            json={"text": "Foreign", "client_key": str(uuid.uuid4())},
        ).status_code
        == 404
    )
    assert (
        client.post(
            base + "/actions",
            headers=headers[2],
            json={
                "action": "cancel",
                "row_version": 1,
                "client_key": str(uuid.uuid4()),
            },
        ).status_code
        == 404
    )


@pytest.mark.parametrize("false_consent", [False, 0, 1, "true", "false"])
def test_publication_requires_literal_boolean_consent(exchange_accounts, false_consent):
    client, headers = exchange_accounts
    result = client.post(
        "/api/exchange/listings",
        headers=headers[0],
        json={**notice(), "consent_to_publish": false_consent},
    )
    assert result.status_code == 422, result.text


def test_reconnect_is_same_thread_and_message_key_cannot_change_words(
    exchange_accounts,
):
    client, headers = exchange_accounts
    listing, thread = setup_thread(client, headers)
    again = client.post(
        "/api/exchange/conversations",
        headers=headers[1],
        json={"listing_id": listing["id"], "consent_to_share_display_name": True},
    )
    assert again.json()["id"] == thread["id"]
    endpoint = "/api/exchange/conversations/" + thread["id"] + "/messages"
    message = {"text": "Can we arrange a handover?", "client_key": str(uuid.uuid4())}
    original = client.post(endpoint, headers=headers[1], json=message)
    assert original.status_code == 200, original.text
    replay = client.post(endpoint, headers=headers[1], json=message)
    assert replay.json()["sequence"] == original.json()["sequence"]
    assert (
        client.post(
            endpoint, headers=headers[1], json={**message, "text": "Changed content"}
        ).status_code
        == 409
    )


def test_author_cannot_accept_and_replaced_proposal_needs_current_version(
    exchange_accounts,
):
    client, headers = exchange_accounts
    _, thread = setup_thread(client, headers)
    endpoint = "/api/exchange/conversations/" + thread["id"] + "/actions"
    proposal = {
        "action": "propose",
        "row_version": 1,
        "client_key": str(uuid.uuid4()),
        "terms": "One machine for one day; transport arranged together.",
    }
    proposed = client.post(endpoint, headers=headers[1], json=proposal)
    assert proposed.status_code == 200, proposed.text
    assert (
        client.post(
            endpoint,
            headers=headers[1],
            json={
                "action": "accept",
                "row_version": 2,
                "client_key": str(uuid.uuid4()),
            },
        ).status_code
        == 409
    )
    replacement = client.post(
        endpoint,
        headers=headers[1],
        json={
            **proposal,
            "row_version": 2,
            "client_key": str(uuid.uuid4()),
            "terms": "Revised: two hours only.",
        },
    )
    assert replacement.status_code == 200, replacement.text
    assert (
        client.post(
            endpoint,
            headers=headers[0],
            json={
                "action": "accept",
                "row_version": 2,
                "client_key": str(uuid.uuid4()),
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            endpoint,
            headers=headers[0],
            json={
                "action": "complete",
                "row_version": 3,
                "client_key": str(uuid.uuid4()),
            },
        ).status_code
        == 409
    )


def test_agreed_resource_cannot_be_cancelled_or_reallocated_during_dispute(
    exchange_accounts,
):
    client, headers = exchange_accounts
    listing, first = setup_thread(client, headers)
    second = client.post(
        "/api/exchange/conversations",
        headers=headers[2],
        json={"listing_id": listing["id"], "consent_to_share_display_name": True},
    ).json()

    def action(thread, who, kind, terms=""):
        response = client.post(
            "/api/exchange/conversations/" + thread["id"] + "/actions",
            headers=headers[who],
            json={
                "action": kind,
                "row_version": thread["row_version"],
                "client_key": str(uuid.uuid4()),
                "terms": terms,
            },
        )
        return response

    proposed = action(first, 1, "propose", "One machine on Friday, no delivery claim.")
    assert proposed.status_code == 200, proposed.text
    accepted = action(proposed.json(), 0, "accept")
    assert accepted.status_code == 200, accepted.text
    assert action(accepted.json(), 1, "cancel").status_code == 409
    disputed = action(
        accepted.json(), 1, "dispute", "Machine condition needs discussion."
    )
    assert disputed.status_code == 200, disputed.text
    second_proposal = action(second, 2, "propose", "Separate request for this machine.")
    assert second_proposal.status_code == 200, second_proposal.text
    assert action(second_proposal.json(), 0, "accept").status_code == 409
