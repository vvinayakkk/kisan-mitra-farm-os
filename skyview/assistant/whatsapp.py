"""Durable reply-only WhatsApp adapter for the same farm agent and files.

No number is guessed, no unsolicited send is made, and an ambiguous provider send
is never retried automatically. Inbound Twilio receipts are the execution keys.
"""

import asyncio
import base64
import hashlib
import hmac
import io
import json
import logging
import re
import shutil
import subprocess
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from sqlalchemy import text

from skyview.assistant import attachments, engine, models, store, v3_store
from skyview.data.v3 import db
from skyview.languages import speech_language
from skyview.utils.config import get_settings

MIMES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/amr": ".amr",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
}
LIMIT = 5 * 1024 * 1024


def split_response(value, limit=1400):
    # WhatsApp has compact formatting, not Markdown tables/headings/code fences.
    value = (
        re.sub(r"^#{1,6}\s*", "", value, flags=re.MULTILINE)
        .replace("**", "*")
        .replace("```", "")
    )
    chunks = []
    while value:
        if len(value) <= limit:
            chunks.append(value.strip())
            break
        cut = value.rfind("\n", 0, limit)
        if cut < limit // 3:
            cut = value.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(value[:cut].strip())
        value = value[cut:].lstrip()
    if len(chunks) > 1:
        chunks = [f"*{i + 1}/{len(chunks)}*\n" + part for i, part in enumerate(chunks)]
    return chunks


def pending_text(pending):
    if pending["kind"] == "approval":
        args = pending.get("review_labels") or pending.get("arguments", {})
        detail = json.dumps(args, ensure_ascii=False, default=str, indent=2)
        return (
            "*Review before I save this*\n"
            + detail
            + "\n\nReply APPROVE "
            + pending["id"][:6]
            + " to proceed, or CANCEL."
        )
    args = pending.get("arguments", {})
    lines = [args.get("question") or args.get("title") or "A few details will help:"]
    for i, field in enumerate(args.get("fields", []), 1):
        lines.append(
            f"{i}. {field['label']}"
            + (
                " · " + ", ".join(map(str, field.get("options", [])))
                if field.get("options")
                else ""
            )
            + (" · Send a clear photo" if field.get("type") == "photo" else "")
        )
    lines.append(
        "Reply 1=your answer; 2=your answer. You can send a photo separately. CANCEL stops this request."
    )
    return "\n".join(lines)


def request_for(body, state, language, attachment_ids):
    pending = state.get("pending")
    base = {"language": language, "attachment_ids": attachment_ids}
    if not pending:
        return models.RunRequest(
            message=body or "Please review this attached file.", **base
        )
    base["pending_id"] = pending["id"]
    if body.upper() == "CANCEL":
        return models.RunRequest(approval=False, **base)
    if pending["kind"] == "approval":
        if body.upper() != "APPROVE " + pending["id"][:6].upper():
            return None
        return models.RunRequest(approval=True, **base)
    fields = pending.get("arguments", {}).get("fields", [])
    answers = {}
    for item in re.split(r"[;\n]", body):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip().casefold()
        for i, field in enumerate(fields, 1):
            if key in {str(i), field["id"].casefold(), field["label"].casefold()}:
                answers[field["id"]] = value.strip()
    text_fields = [f for f in fields if f.get("type") != "photo"]
    if len(text_fields) == 1 and body and "=" not in body:
        answers[text_fields[0]["id"]] = body
    for field in fields:
        if field.get("type") == "photo" and attachment_ids:
            answers[field["id"]] = attachment_ids[-1]
    if not all(field["id"] in answers for field in fields):
        return None
    return models.RunRequest(answers=answers, **base)


async def download_media(client, url, mime, message_sid):
    settings = get_settings()
    parsed = urlsplit(url)
    # Signed webhooks are necessary, but media fetches remain bounded and allowlisted.
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.twilio.com"
        or not re.fullmatch(
            r"/2010-04-01/Accounts/"
            + re.escape(settings.TWILIO_ACCOUNT_SID)
            + r"/Messages/"
            + re.escape(message_sid)
            + r"/Media/ME[a-fA-F0-9]{32}",
            parsed.path,
        )
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("This media URL is not a Twilio attachment for this message.")
    mime = mime.split(";")[0].strip().lower()
    if mime not in MIMES:
        raise ValueError(
            "Send a JPEG/PNG crop photo, PDF, DOCX, XLSX, PPTX, CSV or a short voice note below 5 MB."
        )
    auth = httpx.BasicAuth(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    for _ in range(3):
        async with client.stream(
            "GET", url, auth=auth, follow_redirects=False
        ) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                url = response.headers.get("location", "")
                target = urlsplit(url)
                host = target.hostname or ""
                if target.scheme != "https" or not (
                    host.endswith((".twiliocdn.com", ".twilio.com", ".amazonaws.com"))
                ):
                    raise ValueError("Attachment redirect is not a trusted media host.")
                auth = None  # Never send account credentials to a CDN.
                continue
            if response.status_code != 200:
                raise ValueError(
                    "The attachment could not be downloaded. Please send it again."
                )
            if int(response.headers.get("content-length", "0")) > LIMIT:
                raise ValueError("Please send a file below 5 MB.")
            chunks = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > LIMIT:
                    raise ValueError("Please send a file below 5 MB.")
                chunks.append(chunk)
            if not size:
                raise ValueError("This attachment is empty.")
            return b"".join(chunks), mime
    raise ValueError("Attachment redirected too many times.")


def media_url(owner, file_key, mime, filename):
    from skyview.api.v3_whatsapp_routes import public_base

    identifier = str(uuid.uuid4())
    expires = int(time.time()) + 900
    signature = hmac.new(
        get_settings().TWILIO_AUTH_TOKEN.encode(),
        f"{owner}:{identifier}:{expires}".encode(),
        hashlib.sha256,
    ).hexdigest()
    with db.connection(owner, write=True) as conn:
        conn.execute(
            text(
                "INSERT INTO sv3.whatsapp_media_assets(id,farmer_id,file_key,mime,filename,expires_at) VALUES(:id,:owner,:file,:mime,:name,:expiry)"
            ),
            {
                "id": identifier,
                "owner": owner,
                "file": file_key,
                "mime": mime,
                "name": filename,
                "expiry": datetime.fromtimestamp(expires, UTC),
            },
        )
    return f"{public_base()}/webhook/whatsapp/media/{identifier}?owner={owner}&expires={expires}&signature={signature}"


def binary_media(owner, content, mime, extension, name):
    identifier = uuid.uuid4().hex
    folder = store.ROOT / "whatsapp"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (identifier + extension)
    path.write_bytes(content)
    path.chmod(0o600)
    return media_url(owner, str(path.relative_to(store.ROOT)), mime, name)


def chart_image(chart, source):
    from PIL import Image, ImageDraw

    points = chart.get("points", [])[-365:]
    values = [float(p["value"]) for p in points]
    if len(values) < 2:
        return None
    image = Image.new("RGB", (1000, 520), "#f7faf3")
    draw = ImageDraw.Draw(image)
    title = (
        str(chart.get("title", "Market trend"))
        .encode("ascii", "replace")
        .decode()[:100]
    )
    draw.text((40, 25), title, fill="#29452f")
    draw.text((40, 48), str(chart.get("unit", "INR/quintal")), fill="#52684d")
    low, high = min(values), max(values)
    spread = max(1, high - low)
    coords = [
        (60 + i * 880 / (len(values) - 1), 420 - (v - low) * 310 / spread)
        for i, v in enumerate(values)
    ]
    for y in (110, 210, 310, 420):
        draw.line((60, y, 940, y), fill="#dce5d4")
    draw.line(coords, fill="#365c34", width=4)
    draw.text((60, 445), str(points[0]["date"]), fill="#52684d")
    draw.text((850, 445), str(points[-1]["date"]), fill="#52684d")
    draw.text(
        (60, 480), str(source).encode("ascii", "replace").decode()[:125], fill="#52684d"
    )
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def normalize_voice(content):
    executable = shutil.which("ffmpeg")
    if not executable:
        raise ValueError(
            "Voice-note decoding is unavailable. Please type your question."
        )
    result = subprocess.run(
        [
            executable,
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-t",
            "61",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            "pipe:1",
        ],
        input=content,
        capture_output=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0 or len(result.stdout) < 44:
        raise ValueError("This voice note could not be read. Please record it again.")
    # PCM16 mono 16kHz has exactly 32000 bytes/second after its short WAV header.
    if len(result.stdout) > 60 * 32000 + 256:
        raise ValueError("Please send a voice note shorter than one minute.")
    return result.stdout


def _session(owner):
    with db.connection(owner, write=True) as conn:
        row = conn.execute(
            text(
                "SELECT session_id FROM sv3.whatsapp_connections WHERE disconnected_at IS NULL FOR UPDATE"
            )
        ).first()
        if row is None:
            raise ValueError("WhatsApp was disconnected.")
        sid = row[0]
        if not sid:
            sid = v3_store.create_session_for_farmer(owner)["id"]
            conn.execute(
                text("UPDATE sv3.whatsapp_connections SET session_id=:sid"),
                {"sid": sid},
            )
        profile = conn.execute(
            text("SELECT preferred_language FROM sv3.farmers WHERE id=:owner"),
            {"owner": owner},
        ).scalar()
    from skyview.languages import preferred_language

    return sid, preferred_language(profile)


async def send_part(client, job, part, body="", media=None):
    settings = get_settings()
    owner = str(job["farmer_id"])
    with db.connection(owner, write=True) as conn:
        connected = conn.execute(
            text(
                "SELECT 1 FROM sv3.whatsapp_connections WHERE disconnected_at IS NULL AND sender_number=:sender AND last_received_at>now()-interval '24 hours'"
            ),
            {"sender": job["sender_number"]},
        ).scalar()
        if not connected:
            raise ValueError("The farmer disconnected or the reply window ended.")
        inserted = conn.execute(
            text(
                "INSERT INTO sv3.whatsapp_outbound(farmer_id,message_sid,part,status) VALUES(:owner,:id,:part,'sending') ON CONFLICT DO NOTHING RETURNING id"
            ),
            {"owner": owner, "id": job["message_sid"], "part": part},
        ).scalar()
        if inserted is None:
            return  # Never replay an ambiguous provider send.
    data = {
        "To": job["sender_number"],
        "From": "whatsapp:" + settings.TWILIO_WHATSAPP_NUMBER.removeprefix("whatsapp:"),
        "StatusCallback": __import__(
            "skyview.api.v3_whatsapp_routes", fromlist=["public_base"]
        ).public_base()
        + "/webhook/whatsapp/status",
    }
    if media:
        data["MediaUrl"] = media
    else:
        data["Body"] = body
    try:
        response = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json",
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            data=data,
        )
        if response.status_code not in {200, 201}:
            raise ValueError(
                "Twilio rejected this reply (" + str(response.status_code) + ")."
            )
        payload = response.json()
        provider_sid = payload.get("sid")
        if not isinstance(provider_sid, str) or not re.fullmatch(
            r"(SM|MM)[a-fA-F0-9]{32}", provider_sid
        ):
            raise ValueError("Twilio did not return a valid delivery receipt.")
        status = "accepted"
        error = None
    except Exception as exc:
        with db.connection(owner, write=True) as conn:
            conn.execute(
                text(
                    "UPDATE sv3.whatsapp_outbound SET status='unknown',safe_error=:error,updated_at=now() WHERE id=:id"
                ),
                {"id": inserted, "error": type(exc).__name__},
            )
        raise
    with db.connection(owner, write=True) as conn:
        conn.execute(
            text(
                "UPDATE sv3.whatsapp_outbound SET provider_sid=:sid,status=:status,safe_error=:error,updated_at=now() WHERE id=:id"
            ),
            {"id": inserted, "sid": provider_sid, "status": status, "error": error},
        )


async def process_next():
    from skyview.api.v3_whatsapp_routes import public_base

    settings = get_settings()
    if not public_base() or not all(
        (
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
            settings.TWILIO_WHATSAPP_NUMBER,
        )
    ):
        return False
    with db.connection(ingest=True, write=True) as conn:
        row = (
            conn.execute(text("SELECT * FROM sv3.whatsapp_claim_job()"))
            .mappings()
            .first()
        )
    if not row:
        return False
    job = dict(row)
    owner = str(job["farmer_id"])
    lease = None
    sid = None
    try:
        sid, language = await asyncio.to_thread(_session, owner)
        lease = await asyncio.to_thread(store.claim_run, sid)
        if not lease:
            raise ValueError(
                "Your WhatsApp conversation is already processing a request."
            )
        state = await asyncio.to_thread(store.load, sid)
        before = {a["file_id"] for a in store.records(sid, "artifact")}
        body = job["body"]
        file_ids = []
        was_audio = False
        charts = []
        async with httpx.AsyncClient(timeout=httpx.Timeout(12, connect=5)) as client:
            for item in job["media"]:
                content, mime = await download_media(
                    client, item["url"], item["mime"], job["message_sid"]
                )
                if mime.startswith("audio/"):
                    from skyview.api.v3_voice_routes import transcribe_content

                    content = await asyncio.to_thread(normalize_voice, content)
                    transcript = await transcribe_content(
                        content, "audio/wav", speech_language(language)
                    )
                    body = (body + "\n" + transcript["transcript"]).strip()
                    was_audio = True
                else:
                    attachment = await asyncio.to_thread(
                        attachments.extract,
                        sid,
                        "WhatsApp attachment" + MIMES[mime],
                        content,
                    )
                    file_ids.append(attachment["id"])
            req = request_for(body, state, language, file_ids)
            if req is None:
                response_text = pending_text(state["pending"])
            else:
                engine.preflight(state, req)
                pieces = []
                async with asyncio.timeout(100):
                    async for event in engine.run(sid, req, state):
                        if event["type"] == "delta":
                            pieces.append(event["text"])
                        if event["type"] == "tool_completed" and event.get(
                            "result", {}
                        ).get("chart"):
                            charts.append(event["result"])
                        if event["type"] == "error":
                            pieces.append(
                                event.get(
                                    "message",
                                    "This request could not finish. Please try again.",
                                )
                            )
                response_text = "".join(pieces).strip()
                if state.get("pending"):
                    response_text += "\n\n" + pending_text(state["pending"])
            response_text = (
                response_text.strip()
                or "Your request was saved. Open SkyView for the latest details."
            )
            if was_audio:
                response_text = "*Heard you*\n" + body + "\n\n" + response_text
            parts = split_response(response_text)
            if len(parts) > 12:
                from skyview.assistant.artifacts import create_file

                sections = [
                    models.Section(
                        heading="Farm advice " + str(i // 4500 + 1),
                        text=response_text[i : i + 4500],
                    )
                    for i in range(0, min(len(response_text), 90000), 4500)
                ]
                await asyncio.to_thread(
                    create_file,
                    sid,
                    models.FileArgs(
                        format="pdf", title="Full farm response", sections=sections
                    ),
                )
                parts = parts[:2] + ["The complete answer is attached as a PDF."]
            part = 0
            for message in parts:
                await send_part(client, job, part, body=message)
                part += 1
            for artifact in [
                a for a in store.records(sid, "artifact") if a["file_id"] not in before
            ][:5]:
                url = await asyncio.to_thread(
                    media_url,
                    owner,
                    "files/" + artifact["file_id"] + "." + artifact["format"],
                    artifact["mime"],
                    artifact["filename"],
                )
                await send_part(client, job, part, body="*" + artifact["title"] + "*")
                part += 1
                await send_part(client, job, part, media=url)
                part += 1
            for result in charts[:2]:
                png = await asyncio.to_thread(
                    chart_image,
                    result["chart"],
                    result.get("source", "Dated market observations"),
                )
                if png:
                    url = await asyncio.to_thread(
                        binary_media,
                        owner,
                        png,
                        "image/png",
                        ".png",
                        "Market trend.png",
                    )
                    await send_part(client, job, part, media=url)
                    part += 1
            if was_audio and settings.SARVAM_AI_API_KEY and shutil.which("ffmpeg"):
                try:
                    from skyview.api.v3_voice_routes import Speech, synthesize

                    voice = await synthesize(
                        Speech(
                            text=response_text[:1800],
                            language=speech_language(language),
                        )
                    )
                    wav = base64.b64decode(voice["audio"])
                    folder = store.ROOT / "whatsapp"
                    folder.mkdir(parents=True, exist_ok=True)
                    output = folder / (uuid.uuid4().hex + ".mp3")
                    result = await asyncio.to_thread(
                        subprocess.run,
                        [
                            shutil.which("ffmpeg"),
                            "-loglevel",
                            "error",
                            "-i",
                            "pipe:0",
                            "-codec:a",
                            "libmp3lame",
                            "-b:a",
                            "64k",
                            "-y",
                            str(output),
                        ],
                        input=wav,
                        capture_output=True,
                        timeout=15,
                        check=False,
                    )
                    if result.returncode == 0:
                        url = await asyncio.to_thread(
                            media_url,
                            owner,
                            str(output.relative_to(store.ROOT)),
                            "audio/mpeg",
                            "Spoken summary.mp3",
                        )
                        await send_part(client, job, part, body="Spoken summary")
                        part += 1
                        await send_part(client, job, part, media=url)
                except Exception as exc:  # noqa: BLE001 -- optional speech failure must not discard delivered text
                    logging.getLogger(__name__).warning(
                        "WhatsApp speech unavailable (%s)", type(exc).__name__
                    )
        with db.connection(owner, write=True) as conn:
            conn.execute(
                text(
                    "UPDATE sv3.whatsapp_jobs SET state='replied',finished_at=now() WHERE message_sid=:id"
                ),
                {"id": job["message_sid"]},
            )
    except Exception as exc:  # noqa: BLE001 -- isolate a single durable inbound job
        # Do not log phone numbers, signed media URLs, transcripts, tokens or provider errors.
        try:
            with db.connection(owner) as conn:
                sent = conn.execute(
                    text(
                        "SELECT count(*) FROM sv3.whatsapp_outbound WHERE message_sid=:id"
                    ),
                    {"id": job["message_sid"]},
                ).scalar()
            if not sent:
                friendly = (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else "I could not finish this request. Please resend a smaller file or type your question."
                )
                async with httpx.AsyncClient(timeout=12) as client:
                    await send_part(client, job, 0, body=friendly[:1400])
        except Exception as feedback_error:  # noqa: BLE001 -- a provider outage also prevents the fallback reply
            logging.getLogger(__name__).warning(
                "WhatsApp reply unavailable (%s)", type(feedback_error).__name__
            )
        with db.connection(owner, write=True) as conn:
            conn.execute(
                text(
                    "UPDATE sv3.whatsapp_jobs SET state='failed',safe_error=:error,finished_at=now() WHERE message_sid=:id"
                ),
                {"id": job["message_sid"], "error": type(exc).__name__},
            )
    finally:
        if lease and sid:
            await asyncio.to_thread(store.release_run, sid, lease)
    return True
