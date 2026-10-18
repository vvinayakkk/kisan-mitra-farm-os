import asyncio

import pytest

from skyview.assistant import engine, models, provider, store
from skyview.assistant.fast_actions import task_command
from skyview.assistant.progress import live_events


@pytest.mark.parametrize(
    "text",
    [
        "Don't add a task called Water on 2026-10-20",
        "Add a task called Water and spray on 2026-10-20",
        "Add a task called Water on 2026-13-20",
        "If it rains add a task called Water on 2026-10-20",
        "Add a task called Water on 2026-10-20 and delete all tasks",
        "Can you explain how to add a task called Water on 2026-10-20?",
    ],
)
def test_ambiguous_actions_stay_with_agent(text):
    assert task_command(models.RunRequest(message=text)) is None


def test_non_english_request_does_not_get_english_fast_reply():
    assert (
        task_command(
            models.RunRequest(
                message="Add a task called Water on 2026-10-20", language="hi"
            )
        )
        is None
    )


@pytest.mark.asyncio
async def test_explicit_task_saved_without_model_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path)

    async def forbidden(*args, **kwargs):
        raise AssertionError("Explicit task must not need the language model")
        yield

    monkeypatch.setattr(provider, "stream_turn", forbidden)
    sid = store.create_session()["id"]
    events = [
        e
        async for e in engine.run(
            sid,
            models.RunRequest(message="Add a task called Inspect leaves on 2026-10-20"),
            store.load(sid),
        )
    ]
    assert events[-1]["status"] == "completed"
    assert store.records(sid, "task")[0]["title"] == "Inspect leaves"
    assert any(e["type"] == "tool_completed" and e["result"]["saved"] for e in events)
    assert "2026-10-20" in "".join(e.get("text", "") for e in events)


@pytest.mark.asyncio
async def test_progress_reports_wait_without_replaying_actions():
    async def slow():
        yield {
            "type": "tool_started",
            "label": "Reading prices",
            "arguments": {"commodity": "Wheat"},
        }
        await asyncio.sleep(0.025)
        yield {"type": "tool_completed"}

    events = [e async for e in live_events(slow(), interval=0.005)]
    assert sum(e["type"] == "tool_started" for e in events) == 1
    assert any(e.get("phase") == "waiting" and "Wheat" in e["label"] for e in events)
    assert events[-1]["type"] == "tool_completed"
