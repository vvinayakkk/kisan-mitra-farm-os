"""Signed WhatsApp ingress, owner linking, delivery receipts and expiring media."""

import base64
import hashlib
import hmac
import os
import re
import secrets
import time
from urllib.parse import parse_qsl, urlsplit
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy import text
from starlette.datastructures import FormData

from skyview.api.v3_routes import Owner
from skyview.data.v3 import db, repository
from skyview.utils.config import get_settings

router = APIRouter(tags=["WhatsApp companion"])


def public_base():
    value = os.getenv("SKYVIEW_PUBLIC_URL", "").rstrip("/")
    if not value:
        value = (
            os.getenv("WHATSAPP_WEBHOOK_URL", "")
            .removesuffix("/webhook/whatsapp")
            .rstrip("/")
        )
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return ""
    return value


def channel_summary(conn):
    item = repository.rows(
        conn,
        "SELECT connected_at,last_received_at,disconnected_at,sender_number FROM sv3.whatsapp_connections LIMIT 1",
    )
    settings = get_settings()
    configured = bool(
        settings.TWILIO_ACCOUNT_SID
        and settings.TWILIO_AUTH_TOKEN
        and settings.TWILIO_WHATSAPP_NUMBER
        and public_base()
    )
    row = item[0] if item else None
    connected = bool(row and row["disconnected_at"] is None)
    return {
        "configured": configured,
        "connected": connected,
        "enabled": connected,
        "masked_number": ("•••• " + row["sender_number"][-4:]) if row else None,
        "last_received_at": row["last_received_at"] if row else None,
        "proactive_enabled": False,
        "mode": "Reply to farmer messages",
        "webhook_url": public_base() + "/webhook/whatsapp" if public_base() else None,
    }


@router.get("/api/whatsapp")
def channel(owner: Owner):
    with db.connection(owner) as conn:
        result = channel_summary(conn)
        result["recent_deliveries"] = repository.rows(
            conn,
            "SELECT id,part,status,updated_at,safe_error FROM sv3.whatsapp_outbound ORDER BY created_at DESC LIMIT 12",
        )
    return result


@router.post("/api/whatsapp/link")
def link(owner: Owner):
    settings = get_settings()
    if not (
        settings.TWILIO_ACCOUNT_SID
        and settings.TWILIO_AUTH_TOKEN
        and settings.TWILIO_WHATSAPP_NUMBER
        and public_base()
    ):
        raise HTTPException(
            503, "WhatsApp needs a public HTTPS webhook and configured Twilio sender."
        )
    code = secrets.token_hex(6).upper()
    digest = hashlib.sha256(code.encode()).hexdigest()
    with db.connection(owner, write=True) as conn:
        conn.execute(text("DELETE FROM sv3.whatsapp_link_codes WHERE used_at IS NULL"))
        conn.execute(
            text(
                "INSERT INTO sv3.whatsapp_link_codes(token_hash,farmer_id,expires_at) VALUES(:hash,:owner,now()+interval '10 minutes')"
            ),
            {"hash": digest, "owner": owner},
        )
    number = settings.TWILIO_WHATSAPP_NUMBER.replace("whatsapp:", "").replace("+", "")
    return {
        "code": code,
        "message": "LINK " + code,
        "expires_in_seconds": 600,
        "url": "https://wa.me/" + number + "?text=LINK%20" + code,
    }


@router.delete("/api/whatsapp/link")
def unlink(owner: Owner):
    with db.connection(owner, write=True) as conn:
        conn.execute(text("UPDATE sv3.whatsapp_connections SET disconnected_at=now()"))
        conn.execute(
            text("UPDATE sv3.whatsapp_jobs SET state='cancelled' WHERE state='queued'")
        )
    return {"connected": False}


def twiml(message=""):
    return Response(
        "<Response>"
        + ("<Message>" + escape(message) + "</Message>" if message else "")
        + "</Response>",
        media_type="application/xml",
    )


async def verified_form(request, path):
    settings = get_settings()
    token = settings.TWILIO_AUTH_TOKEN
    expected = (
        os.getenv("WHATSAPP_WEBHOOK_URL", "") if path == "/webhook/whatsapp" else ""
    )
    expected = expected or (public_base() + path if public_base() else "")
    if not token or not expected:
        raise HTTPException(503, "WhatsApp webhook is not configured")
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 64000:
            raise HTTPException(413, "Webhook is too large")
        chunks.append(chunk)
    if not request.headers.get("content-type", "").startswith(
        "application/x-www-form-urlencoded"
    ):
        raise HTTPException(415, "Use Twilio form encoding")
    try:
        form = FormData(
            parse_qsl(
                b"".join(chunks).decode("utf-8"),
                keep_blank_values=True,
                max_num_fields=100,
            )
        )
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(422, "Malformed Twilio form") from exc
    value = expected
    for key in sorted(form):
        for entry in sorted({str(v) for v in form.getlist(key)}):
            value += key + entry
    signature = base64.b64encode(
        hmac.new(token.encode(), value.encode(), hashlib.sha1).digest()
    ).decode()
    if not hmac.compare_digest(
        request.headers.get("X-Twilio-Signature", ""), signature
    ):
        raise HTTPException(403, "Invalid webhook signature")
    if form.get("AccountSid") != settings.TWILIO_ACCOUNT_SID:
        raise HTTPException(403, "Wrong Twilio account")
    return form


@router.post("/webhook/whatsapp")
async def incoming(request: Request):
    form = await verified_form(request, "/webhook/whatsapp")
    settings = get_settings()
    sender = str(form.get("From", ""))
    body = str(form.get("Body", "")).strip()
    if not re.fullmatch(r"whatsapp:\+[1-9][0-9]{7,14}", sender):
        raise HTTPException(422, "Invalid WhatsApp sender")
    expected = "whatsapp:" + settings.TWILIO_WHATSAPP_NUMBER.removeprefix("whatsapp:")
    if form.get("To") != expected:
        raise HTTPException(403, "Wrong WhatsApp recipient")
    sid = str(form.get("MessageSid", ""))
    if not re.fullmatch(r"(SM|MM)[a-fA-F0-9]{32}", sid):
        raise HTTPException(422, "Invalid message receipt")
    digest = hmac.new(
        settings.TWILIO_AUTH_TOKEN.encode(), sender.encode(), hashlib.sha256
    ).hexdigest()
    with db.connection(ingest=True, write=True) as conn:
        if re.fullmatch(r"LINK [A-Fa-f0-9]{12}", body, re.IGNORECASE):
            code_hash = hashlib.sha256(body.split()[1].upper().encode()).hexdigest()
            owner = conn.execute(
                text("SELECT sv3.whatsapp_redeem_link(:code,:hash,:phone)"),
                {"code": code_hash, "hash": digest, "phone": sender},
            ).scalar()
            return twiml(
                "Connected to your SkyView farm. Send a question, crop photo, PDF, Word/Excel file or a short voice note. Reply STOP to disconnect."
                if owner
                else "This link code expired or was already used. Generate a new code in SkyView."
            )
        owner = conn.execute(
            text("SELECT sv3.whatsapp_sender(:hash)"), {"hash": digest}
        ).scalar()
    if not owner:
        return twiml(
            "Connect your farm first: open SkyView → Saathi → WhatsApp and send its one-time LINK code here."
        )
    try:
        count = int(form.get("NumMedia", "0"))
    except ValueError as exc:
        raise HTTPException(422, "Invalid media count") from exc
    if not 0 <= count <= 1:
        return twiml("Please send one photo, document or voice note per message.")
    media = (
        [
            {
                "url": str(form.get("MediaUrl0", "")),
                "mime": str(form.get("MediaContentType0", "")),
            }
        ]
        if count
        else []
    )
    with db.connection(str(owner), write=True) as conn:
        if body.upper() == "STOP":
            conn.execute(
                text("UPDATE sv3.whatsapp_connections SET disconnected_at=now()")
            )
            conn.execute(
                text(
                    "UPDATE sv3.whatsapp_jobs SET state='cancelled' WHERE state='queued'"
                )
            )
            return twiml(
                "Disconnected. Your farm data stays in SkyView. Reconnect there whenever you choose."
            )
        conn.execute(text("UPDATE sv3.whatsapp_connections SET last_received_at=now()"))
        import json

        pending = conn.execute(
            text(
                "SELECT count(*) FROM sv3.whatsapp_jobs WHERE state IN ('queued','processing')"
            )
        ).scalar()
        if pending >= 10:
            return twiml(
                "I am finishing your earlier messages. Please wait a moment before sending more."
            )

        conn.execute(
            text(
                "INSERT INTO sv3.whatsapp_jobs(message_sid,farmer_id,sender_number,body,media) VALUES(:id,:owner,:sender,:body,CAST(:media AS jsonb)) ON CONFLICT DO NOTHING"
            ),
            {
                "id": sid,
                "owner": owner,
                "sender": sender,
                "body": body[:6000],
                "media": json.dumps(media),
            },
        )
    from skyview.data.v3.worker import notify_whatsapp

    notify_whatsapp()
    return twiml()


@router.post("/webhook/whatsapp/status")
async def delivery_status(request: Request):
    form = await verified_form(request, "/webhook/whatsapp/status")
    sid = str(form.get("MessageSid", ""))
    status = str(form.get("MessageStatus", ""))
    if status not in {
        "queued",
        "sending",
        "sent",
        "delivered",
        "read",
        "failed",
        "undelivered",
    }:
        return twiml()

    with db.connection(ingest=True) as conn:
        owner = conn.execute(
            text("SELECT sv3.whatsapp_delivery_owner(:sid)"), {"sid": sid}
        ).scalar()
    if owner:
        with db.connection(str(owner), write=True) as conn:
            conn.execute(
                text("""UPDATE sv3.whatsapp_outbound SET status=:status,updated_at=now(),safe_error=:error WHERE provider_sid=:sid
             AND CASE status WHEN 'accepted' THEN 1 WHEN 'queued' THEN 2 WHEN 'sending' THEN 3 WHEN 'sent' THEN 4
             WHEN 'failed' THEN 5 WHEN 'undelivered' THEN 5 WHEN 'delivered' THEN 6 WHEN 'read' THEN 7 ELSE 0 END
             <= CASE :status WHEN 'queued' THEN 2 WHEN 'sending' THEN 3 WHEN 'sent' THEN 4 WHEN 'failed' THEN 5
             WHEN 'undelivered' THEN 5 WHEN 'delivered' THEN 6 WHEN 'read' THEN 7 ELSE 0 END"""),
                {
                    "sid": sid,
                    "status": status,
                    "error": str(form.get("ErrorCode", ""))[:20] or None,
                },
            )
    return twiml()


@router.api_route("/webhook/whatsapp/media/{identifier}", methods=["GET", "HEAD"])
def media_file(identifier: str, owner: str, expires: int, signature: str):
    import uuid

    try:
        uuid.UUID(identifier)
        uuid.UUID(owner)
    except ValueError as exc:
        raise HTTPException(404, "Media unavailable") from exc
    expected = hmac.new(
        get_settings().TWILIO_AUTH_TOKEN.encode(),
        f"{owner}:{identifier}:{expires}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if (
        expires < int(time.time())
        or expires > int(time.time()) + 960
        or not hmac.compare_digest(signature, expected)
    ):
        raise HTTPException(403, "Media link expired")
    with db.connection(owner) as conn:
        items = repository.rows(
            conn,
            "SELECT file_key,mime,filename FROM sv3.whatsapp_media_assets WHERE id=:id AND expires_at>now()",
            {"id": identifier},
        )
    if not items:
        raise HTTPException(404, "Media unavailable")
    from pathlib import Path

    from skyview.assistant import store

    item = items[0]
    path = (store.ROOT / item["file_key"]).resolve()
    if not path.is_relative_to(store.ROOT.resolve()) or not path.is_file():
        raise HTTPException(404, "Media unavailable")
    return FileResponse(
        path,
        media_type=item["mime"],
        filename=Path(item["filename"]).name,
        headers={"Cache-Control": "no-store"},
    )
