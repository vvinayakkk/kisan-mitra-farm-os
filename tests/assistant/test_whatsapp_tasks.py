from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from google.cloud import tasks_v2

from skyview.assistant import whatsapp_tasks


def test_enqueue_uses_authenticated_task_and_deduplicated_receipt(monkeypatch):
    sent = []
    monkeypatch.setenv("WHATSAPP_TASK_QUEUE", "projects/farm/locations/asia-south1/queues/whatsapp")
    monkeypatch.setenv("WHATSAPP_TASK_SERVICE_ACCOUNT", "tasks@farm.iam.gserviceaccount.com")
    monkeypatch.setenv("SKYVIEW_PUBLIC_URL", "https://api.example.run.app")
    monkeypatch.setattr(tasks_v2, "CloudTasksClient", lambda: SimpleNamespace(create_task=lambda **kwargs: sent.append(kwargs)))
    sid = "SM" + "a" * 32
    whatsapp_tasks.enqueue(sid)
    assert len(sent) == 1
    assert sent[0]["task"]["name"].endswith("/tasks/" + sid)
    assert sent[0]["task"]["http_request"]["oidc_token"]["audience"] == "https://api.example.run.app"
    assert sent[0]["task"]["http_request"]["url"].endswith("/internal/whatsapp/drain")


def test_worker_identity_rejects_wrong_service_account(monkeypatch):
    from google.oauth2 import id_token

    monkeypatch.setenv("WHATSAPP_TASK_SERVICE_ACCOUNT", "tasks@farm.iam.gserviceaccount.com")
    monkeypatch.setenv("SKYVIEW_PUBLIC_URL", "https://api.example.run.app")
    monkeypatch.setattr(id_token, "verify_oauth2_token", lambda *args, **kwargs: {
        "email": "other@farm.iam.gserviceaccount.com",
        "email_verified": True,
    })
    request = SimpleNamespace(headers={"Authorization": "Bearer signed-token"})
    with pytest.raises(HTTPException) as error:
        whatsapp_tasks.verify_task(request)
    assert error.value.status_code == 403
