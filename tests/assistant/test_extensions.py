import io

import httpx
import pytest
from PIL import Image, UnidentifiedImageError

from skyview.assistant import attachments, memory, store
from skyview.assistant.tools import Executor, public_catalog


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path)


def photo():
    stream = io.BytesIO()
    Image.new("RGB", (32, 32), "green").save(stream, "PNG")
    return stream.getvalue()


@pytest.mark.asyncio
async def test_owned_crop_photo_and_real_vision_failure(monkeypatch):
    sid = store.create_session()["id"]
    other = store.create_session()["id"]
    uploaded = attachments.extract(sid, "leaf.png", photo())

    async def diagnose(content):
        assert content == photo()
        return {"disease_name": "Unknown", "confidence": 0}

    monkeypatch.setattr("skyview.agents.disease_service.analyze_crop_image", diagnose)
    async with httpx.AsyncClient() as client:
        result = await Executor(sid, "WS01", client).run(
            "diagnose_crop", {"file_id": uploaded["id"]}
        )
        assert result["diagnostic"]["confidence"] == 0
        with pytest.raises(ValueError, match="Attach"):
            await Executor(other, "WS01", client).run(
                "diagnose_crop", {"file_id": uploaded["id"]}
            )
    with pytest.raises(UnidentifiedImageError):
        attachments.extract(sid, "fake.png", b"not an image")


@pytest.mark.asyncio
async def test_market_series_does_not_mix_markets(monkeypatch):
    sid = store.create_session()["id"]
    rows = [
        {
            "market": "A",
            "variety": "V",
            "unit": "INR/quintal",
            "arrival_date": "2026-10-12",
            "modal_price": 100,
        },
        {
            "market": "A",
            "variety": "V",
            "unit": "INR/quintal",
            "arrival_date": "2026-10-13",
            "modal_price": 120,
        },
        {
            "market": "B",
            "variety": "V",
            "arrival_date": "2026-10-12",
            "modal_price": 9999,
        },
    ]

    async def upstream(*args):
        return {"records": rows}

    async with httpx.AsyncClient() as client:
        ex = Executor(sid, "WS01", client)
        monkeypatch.setattr(ex, "upstream", upstream)
        result = await ex.run("market_trend", {"commodity": "Wheat"})
        assert [p["value"] for p in result["chart"]["points"]] == [100, 120]
        rows.clear()
        result = await ex.run("market_trend", {"commodity": "Rice"})
        assert result["chart"] is None and result["available"] is False


@pytest.mark.asyncio
async def test_compaction_keeps_full_archive_and_tool_contracts(monkeypatch):
    sid = store.create_session()["id"]
    messages = []
    for i in range(8):
        messages.extend(
            [
                {"role": "user", "content": f"turn {i}" + " long fact" * 100},
                {"role": "assistant", "content": "result"},
            ]
        )
    state = {"messages": messages, "pending": None}
    original = list(messages)
    monkeypatch.setattr(memory, "CONTEXT_BUDGET", 1000)

    async def summarize(*args):
        yield {
            "type": "turn",
            "message": {
                "role": "assistant",
                "content": "Farmer's earlier evidence, with uncertainty.",
            },
        }

    monkeypatch.setattr(memory.provider, "stream_turn", summarize)
    async with httpx.AsyncClient() as client:
        result = await memory.context(client, sid, state)
    assert state["compactions"] == 1
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user"
    assert state["messages"] == original
    assert store.load(sid)["memory_summary"]


@pytest.mark.asyncio
async def test_memory_retrieval_scoped_to_workspace():
    sid = store.create_session()["id"]
    other = store.create_session()["id"]
    state = {
        "messages": [{"role": "user", "content": "I prefer organic scouting"}],
        "pending": None,
        "display_history": [{"role": "user", "content": "I prefer organic scouting"}],
    }
    store.save(sid, state)
    store.archive_conversation(sid)
    async with httpx.AsyncClient() as client:
        result = await Executor(sid, "WS01", client).run(
            "recall_memory", {"query": "organic"}
        )
        assert len(result["memories"]) == 1
        result = await Executor(other, "WS01", client).run(
            "recall_memory", {"query": "organic"}
        )
        assert result["memories"] == []
    assert all(s["workflow"] for s in public_catalog()["skills"])


@pytest.mark.asyncio
async def test_crop_doctor_never_fabricates_on_bad_image():
    from skyview.agents.disease_service import analyze_crop_image

    with pytest.raises(ValueError):
        await analyze_crop_image(b"not a photo")


@pytest.mark.asyncio
async def test_native_stream_accepts_missing_tool_indices(monkeypatch):
    import json
    from types import SimpleNamespace

    from skyview.assistant import provider

    monkeypatch.setattr(
        provider,
        "get_settings",
        lambda: SimpleNamespace(GROQ_API_KEYS=["test"], GEMINI_API_KEY=None),
    )
    packets = [
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "id": "call",
                                "function": {"name": "list_tasks", "arguments": "{}"},
                            }
                        ]
                    }
                }
            ]
        }
    ]
    text = (
        "".join("data: " + json.dumps(p) + "\n\n" for p in packets) + "data: [DONE]\n\n"
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=text))
    ) as client:
        events = [
            event
            async for event in provider.stream_turn(
                client, [{"role": "user", "content": "Tasks"}], []
            )
        ]
    assert events[-1]["message"]["tool_calls"][0]["function"]["name"] == "list_tasks"


def test_photo_question_requires_owned_file_shape():
    from skyview.assistant import engine, models

    args = models.QuestionArgs(
        question="Attach a crop photo",
        fields=[{"id": "photo", "label": "Affected leaf", "type": "photo"}],
    )
    pending = {"arguments": args.model_dump()}
    with pytest.raises(ValueError, match="Upload"):
        engine.validate_answers(pending, {"photo": "file:///etc/passwd"})
    assert engine.validate_answers(pending, {"photo": "a" * 32})["photo"] == "a" * 32


def test_calendar_edits_delete_restore_are_scoped_and_validated():
    from fastapi.testclient import TestClient

    from skyview.assistant.dev import app

    owner = store.create_session()
    other = store.create_session()
    task = store.add_record(
        owner["id"],
        "task",
        {
            "title": "Public test",
            "due_date": "2026-10-15",
            "notes": "Original note",
            "completed": False,
        },
    )
    headers = {"Authorization": "Bearer " + owner["token"]}
    root = f"/api/assistant/sessions/{owner['id']}/tasks/{task['id']}"
    with TestClient(app) as client:
        response = client.patch(
            root,
            headers=headers,
            json={"title": "Edited", "due_date": "2026-10-16", "notes": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["due_date"] == "2026-10-16"
        assert response.json()["completed"] is False
        assert (
            client.patch(
                root, headers=headers, json={"title": "Edited", "due_date": "invalid"}
            ).status_code
            == 422
        )
        unauthorized = f"/api/assistant/sessions/{other['id']}/tasks/{task['id']}"
        assert (
            client.delete(
                unauthorized, headers={"Authorization": "Bearer " + other["token"]}
            ).status_code
            == 404
        )
        lease = store.claim_run(owner["id"])
        assert client.delete(root, headers=headers).status_code == 409
        store.release_run(owner["id"], lease)
        assert client.delete(root, headers=headers).status_code == 200
        assert store.records(owner["id"], "task") == []
        assert client.delete(root, headers=headers).status_code == 200
        assert client.post(root + "/restore", headers=headers).status_code == 200
        restored = store.records(owner["id"], "task")[0]
        assert restored["title"] == "Edited" and restored["notes"] == "Updated"


@pytest.mark.asyncio
async def test_agent_calendar_mutations_require_review_and_preserve_other_tasks(
    monkeypatch,
):
    from test_assistant import call

    from skyview.assistant import engine, models, provider

    sid = store.create_session()["id"]
    task = store.add_record(
        sid,
        "task",
        {
            "title": "Check field",
            "due_date": "2026-10-15",
            "notes": "Keep these",
            "completed": False,
        },
    )

    async def stream(*args, **kwargs):
        yield {
            "type": "turn",
            "message": call(
                "update_task",
                {
                    "task_id": task["id"],
                    "title": "Check field",
                    "due_date": "2026-10-16",
                    "notes": "Keep these",
                },
            ),
        }

    monkeypatch.setattr(provider, "stream_turn", stream)
    state = store.load(sid)
    events = [
        e
        async for e in engine.run(
            sid, models.RunRequest(message="Move task to tomorrow"), state
        )
    ]
    assert any(e["type"] == "approval" for e in events)
    assert store.records(sid, "task")[0]["due_date"] == "2026-10-15"
    assert state["pending"]["tool"] == "update_task"
