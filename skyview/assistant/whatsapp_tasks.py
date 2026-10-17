"""Request-driven WhatsApp job dispatch for scale-to-zero deployments."""

import asyncio
import os
import re

from fastapi import HTTPException, Request


def enabled() -> bool:
    return bool(os.getenv("WHATSAPP_TASK_QUEUE"))


def enqueue(message_sid: str) -> None:
    from google.api_core.exceptions import AlreadyExists
    from google.cloud import tasks_v2

    queue = os.environ["WHATSAPP_TASK_QUEUE"]
    service_email = os.environ["WHATSAPP_TASK_SERVICE_ACCOUNT"]
    base = os.environ["SKYVIEW_PUBLIC_URL"].rstrip("/")
    if not re.fullmatch(r"projects/[^/]+/locations/[^/]+/queues/[^/]+", queue):
        raise RuntimeError("Invalid WhatsApp task queue")
    if not base.startswith("https://"):
        raise RuntimeError("WhatsApp task target must use HTTPS")
    if not re.fullmatch(r"(?:SM|MM)[a-fA-F0-9]{32}", message_sid):
        raise ValueError("Invalid WhatsApp message receipt")
    client = tasks_v2.CloudTasksClient()
    task = {
        "name": f"{queue}/tasks/{message_sid}",
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": base + "/internal/whatsapp/drain",
            "oidc_token": {
                "service_account_email": service_email,
                "audience": base,
            },
        },
        "dispatch_deadline": {"seconds": 180},
    }
    try:
        client.create_task(parent=queue, task=task)
    except AlreadyExists:
        pass


async def dispatch(message_sid: str) -> None:
    if enabled():
        await asyncio.to_thread(enqueue, message_sid)
    else:
        from skyview.data.v3.worker import notify_whatsapp

        notify_whatsapp()


def verify_service_identity(request: Request, email_variable: str) -> None:
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2.id_token import verify_oauth2_token

    expected_email = os.getenv(email_variable, "")
    audience = os.getenv("SKYVIEW_PUBLIC_URL", "").rstrip("/")
    header = request.headers.get("Authorization", "")
    if not expected_email or not audience or not header.startswith("Bearer "):
        raise HTTPException(403, "Task identity required")
    try:
        claims = verify_oauth2_token(
            header[7:], GoogleRequest(), audience=audience
        )
    except Exception as exc:
        raise HTTPException(403, "Invalid task identity") from exc
    if claims.get("email") != expected_email or claims.get("email_verified") is not True:
        raise HTTPException(403, "Wrong task identity")


def verify_task(request: Request) -> None:
    verify_service_identity(request, "WHATSAPP_TASK_SERVICE_ACCOUNT")
