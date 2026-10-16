"""Signed, owner-linked WhatsApp transport; every external request is mocked."""

import base64
import hashlib
import hmac
import os
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from skyview.api import v3_whatsapp_routes as routes
from skyview.assistant import store, whatsapp
from skyview.data.v3 import db

ACCOUNT = "AC" + "a" * 32
MESSAGE = "SM" + "b" * 32
PHONE = "whatsapp:+919876543210"
TOKEN = "isolated-fake-token"
BASE = "https://farm.example"


def sign(data, path="/webhook/whatsapp"):
    value = BASE + path + "".join(key + str(data[key]) for key in sorted(data))
    return base64.b64encode(
        hmac.new(TOKEN.encode(), value.encode(), hashlib.sha1).digest()
    ).decode()


@pytest.fixture
def channel(monkeypatch, tmp_path):
    url = os.getenv("V3_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires isolated PostgreSQL integration database")
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    monkeypatch.setenv("V3_DATABASE_URL", url)
    monkeypatch.setenv("V3_DEMO_FARMER_KEY", "DEMO-F0089")
    monkeypatch.setenv("SKYVIEW_PUBLIC_URL", BASE)
    monkeypatch.delenv("WHATSAPP_WEBHOOK_URL", raising=False)
    settings = SimpleNamespace(
        TWILIO_ACCOUNT_SID=ACCOUNT,
        TWILIO_AUTH_TOKEN=TOKEN,
        TWILIO_WHATSAPP_NUMBER="+14155238886",
        SARVAM_AI_API_KEY="",
    )
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(whatsapp, "get_settings", lambda: settings)
    monkeypatch.setattr(store, "ROOT", tmp_path)
    session = store.create_session()
    owner = store.farmer_id(session["id"])
    headers = {
        "Authorization": "Bearer " + session["token"],
        "X-Assistant-Session": session["id"],
    }
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        yield client, headers, owner
    with db.connection(owner, write=True) as conn:
        for table in (
            "whatsapp_media_assets",
            "whatsapp_outbound",
            "whatsapp_jobs",
            "whatsapp_link_codes",
            "whatsapp_connections",
        ):
            conn.execute(text("DELETE FROM sv3." + table))


def form(body="Hi", sid=MESSAGE, **kwargs):
    return {
        "AccountSid": ACCOUNT,
        "From": PHONE,
        "To": "whatsapp:+14155238886",
        "MessageSid": sid,
        "Body": body,
        "NumMedia": "0",
        **kwargs,
    }


def connect(client, headers):
    result = client.post("/api/whatsapp/link", headers=headers)
    assert result.status_code == 200
    code = result.json()["message"]
    data = form(code)
    assert (
        client.post(
            "/webhook/whatsapp", data=data, headers={"X-Twilio-Signature": sign(data)}
        ).status_code
        == 200
    )
    return code


def test_signature_link_owner_and_receipt_dedup(channel):
    client, headers, owner = channel
    assert client.get("/api/whatsapp").status_code == 401
    assert client.post("/webhook/whatsapp", data=form()).status_code == 403
    code = connect(client, headers)
    assert client.get("/api/whatsapp", headers=headers).json()["connected"] is True
    assert PHONE not in client.get("/api/whatsapp", headers=headers).text
    data = form("Check my crops")
    for _ in range(2):
        response = client.post(
            "/webhook/whatsapp", data=data, headers={"X-Twilio-Signature": sign(data)}
        )
        assert response.status_code == 200 and response.text == "<Response></Response>"
    with db.connection(owner) as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM sv3.whatsapp_jobs WHERE message_sid=:sid"),
                {"sid": MESSAGE},
            ).scalar()
            == 1
        )
    used = form(code, sid="SM" + "c" * 32)
    assert (
        "expired"
        in client.post(
            "/webhook/whatsapp", data=used, headers={"X-Twilio-Signature": sign(used)}
        ).text
    )
    stopped = form("STOP", sid="SM" + "d" * 32)
    client.post(
        "/webhook/whatsapp", data=stopped, headers={"X-Twilio-Signature": sign(stopped)}
    )
    assert client.get("/api/whatsapp", headers=headers).json()["connected"] is False


@pytest.mark.asyncio
async def test_queue_same_agent_rich_chunks_and_delivery_receipts(channel, monkeypatch):
    client, headers, owner = channel
    connect(client, headers)
    data = form("What can you do?")
    client.post(
        "/webhook/whatsapp", data=data, headers={"X-Twilio-Signature": sign(data)}
    )

    async def agent(sid, req, state):
        assert req.message == "What can you do?"
        yield {"type": "delta", "text": "I can help plan your farm. " * 100}
        yield {"type": "done", "status": "completed"}

    monkeypatch.setattr(whatsapp.engine, "run", agent)
    sent = []

    def transport(request):
        assert request.url.host == "api.twilio.com" and request.method == "POST"
        sent.append(request.content)
        return httpx.Response(
            201, json={"sid": "SM" + format(len(sent), "032x"), "status": "queued"}
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        whatsapp.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs),
    )
    assert await whatsapp.process_next()
    assert not await whatsapp.process_next()
    assert len(sent) >= 2
    with db.connection(owner) as conn:
        assert (
            conn.execute(
                text("SELECT state FROM sv3.whatsapp_jobs WHERE message_sid=:sid"),
                {"sid": MESSAGE},
            ).scalar()
            == "replied"
        )
        assert conn.execute(
            text("SELECT count(*) FROM sv3.whatsapp_outbound WHERE status='accepted'")
        ).scalar() == len(sent)
    callback = {
        "AccountSid": ACCOUNT,
        "MessageSid": "SM" + format(1, "032x"),
        "MessageStatus": "delivered",
    }
    assert (
        client.post(
            "/webhook/whatsapp/status",
            data=callback,
            headers={"X-Twilio-Signature": sign(callback, "/webhook/whatsapp/status")},
        ).status_code
        == 200
    )
    assert (
        client.get("/api/whatsapp", headers=headers).json()["recent_deliveries"][-1][
            "status"
        ]
        == "delivered"
    )


@pytest.mark.asyncio
async def test_media_host_credentials_and_size_are_bounded(channel):
    _client, _headers, _owner = channel
    requests = []

    def transport(request):
        requests.append(request)
        if request.url.host == "api.twilio.com":
            return httpx.Response(
                302, headers={"location": "https://media.twiliocdn.com/photo"}
            )
        assert "authorization" not in request.headers
        return httpx.Response(
            200, content=b"example", headers={"content-type": "image/jpeg"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT}/Messages/{MESSAGE}/Media/ME"
            + ("e" * 32)
        )
        content, mime = await whatsapp.download_media(
            client, url, "image/jpeg", MESSAGE
        )
        assert content == b"example" and mime == "image/jpeg" and len(requests) == 2
        with pytest.raises(ValueError):
            await whatsapp.download_media(
                client, "http://127.0.0.1/private", "image/jpeg", MESSAGE
            )
        with pytest.raises(ValueError):
            await whatsapp.download_media(client, url, "application/zip", MESSAGE)


def test_signed_media_expiration_and_pending_approval(channel, tmp_path):
    client, _headers, owner = channel
    url = whatsapp.binary_media(
        owner, b"%PDF-1.4\nexample", "application/pdf", ".pdf", "Farm report.pdf"
    )
    from urllib.parse import urlsplit

    path = urlsplit(url).path + "?" + urlsplit(url).query
    response = client.get(path)
    assert (
        response.status_code == 200
        and response.headers["content-type"] == "application/pdf"
    )
    assert client.head(path).status_code == 200
    assert (
        client.get(path.replace("signature=", "signature=invalid")).status_code == 403
    )
    state = {
        "pending": {
            "id": "aabbcc123",
            "kind": "approval",
            "arguments": {"title": "Water crop"},
        }
    }
    assert whatsapp.request_for("APPROVE wrong", state, "en", []) is None
    assert whatsapp.request_for("APPROVE aabbcc", state, "en", []).approval is True
    assert whatsapp.request_for("CANCEL", state, "en", []).approval is False
    parts = whatsapp.split_response("This is a full answer. " * 200)
    assert len(parts) > 1 and all(len(part) < 1600 for part in parts)


@pytest.mark.asyncio
@pytest.mark.parametrize("format", ["pdf", "docx", "xlsx", "pptx", "csv"])
async def test_generated_files_reach_signed_media_download(
    channel, monkeypatch, format
):
    from urllib.parse import parse_qs, urlsplit

    from skyview.assistant import artifacts, models

    client, headers, _owner = channel
    connect(client, headers)
    data = form("Make a farm report")
    client.post(
        "/webhook/whatsapp", data=data, headers={"X-Twilio-Signature": sign(data)}
    )

    async def agent(sid, req, state):
        artifacts.create_file(
            sid,
            models.FileArgs(
                format=format,
                title="Farm report",
                sections=[{"heading": "Plan", "text": "Inspect the field."}],
                columns=["Crop", "Quantity"],
                rows=[["Wheat", 10]],
            ),
        )
        yield {"type": "delta", "text": "Your farm report is ready."}

    monkeypatch.setattr(whatsapp.engine, "run", agent)
    sent = []

    def transport(request):
        sent.append(parse_qs(request.content.decode()))
        return httpx.Response(
            201, json={"sid": "SM" + format_sid(len(sent)), "status": "queued"}
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        whatsapp.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs),
    )
    assert await whatsapp.process_next()
    media = [item["MediaUrl"][0] for item in sent if "MediaUrl" in item]
    assert len(media) == 1
    parsed = urlsplit(media[0])
    response = client.get(parsed.path + "?" + parsed.query)
    assert response.status_code == 200
    assert response.headers["content-type"].split(";")[0] == artifacts.MIME[format]
    assert len(response.content) > 20
    if format in {"docx", "xlsx", "pptx"}:
        assert response.content.startswith(b"PK")
    elif format == "pdf":
        assert response.content.startswith(b"%PDF")


def format_sid(index):
    return f"{index:032x}"


@pytest.mark.asyncio
async def test_relinked_phone_never_receives_older_queued_reply(channel):
    client, headers, owner = channel
    connect(client, headers)
    with db.connection(owner, write=True) as conn:
        conn.execute(
            text(
                "INSERT INTO sv3.whatsapp_jobs(message_sid,farmer_id,sender_number,body,media) VALUES(:sid,:owner,:phone,'Old request','[]')"
            ),
            {"sid": MESSAGE, "owner": owner, "phone": PHONE},
        )
        conn.execute(
            text(
                "UPDATE sv3.whatsapp_connections SET sender_number='whatsapp:+919876543211'"
            )
        )
    requests = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(500)
        )
    ) as http:
        with pytest.raises(ValueError):
            await whatsapp.send_part(
                http,
                {"farmer_id": owner, "message_sid": MESSAGE, "sender_number": PHONE},
                0,
                body="Private farm answer",
            )
    assert requests == []
