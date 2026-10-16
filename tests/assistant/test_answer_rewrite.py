import pytest
from fastapi.testclient import TestClient

from skyview.assistant import provider, store
from skyview.assistant.dev import app


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path)
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "legacy")
    session = store.create_session()
    state = store.load(session["id"])
    state["display_history"] = [
        {"id": "question", "role": "user", "content": "Save my seed expense"},
        {
            "id": "answer",
            "role": "assistant",
            "content": "Saved ₹150 for seeds.",
            "status": "completed",
        },
    ]
    store.save(session["id"], state)
    return session


def invoke(session, identifier="answer"):
    return TestClient(app).post(
        f"/api/assistant/sessions/{session['id']}/answers/{identifier}/rewrite",
        headers={"Authorization": f"Bearer {session['token']}"},
    )


def test_rewrite_uses_no_tools_and_preserves_original(session, monkeypatch):
    before = store.load(session["id"])

    async def stream(client, messages, tools):
        assert tools == []
        assert "Saved ₹150 for seeds." in messages[-1]["content"]
        assert "no tools" in messages[0]["content"]
        yield {
            "type": "turn",
            "message": {
                "role": "assistant",
                "content": "Your seed expense of ₹150 was saved.",
            },
        }

    monkeypatch.setattr(provider, "stream_turn", stream)
    response = invoke(session)
    assert response.status_code == 200
    assert response.json()["tools_executed"] is False
    assert response.json()["saved"] is False
    assert store.load(session["id"]) == before


def test_foreign_answer_and_invalid_session_are_rejected(session, monkeypatch):
    async def forbidden(*args):
        raise AssertionError("Provider must not run")
        yield

    monkeypatch.setattr(provider, "stream_turn", forbidden)
    assert invoke(session, "someone-elses-answer").status_code == 404
    assert invoke({**session, "token": "wrong"}).status_code == 401
    assert invoke(session, "question").status_code == 404


def test_pending_or_older_answer_cannot_be_rewritten(session):
    state = store.load(session["id"])
    state["pending"] = {"kind": "approval"}
    store.save(session["id"], state)
    assert invoke(session).status_code == 409
    state["pending"] = None
    state["display_history"].append(
        {
            "id": "new-answer",
            "role": "assistant",
            "content": "Next",
            "status": "completed",
        }
    )
    store.save(session["id"], state)
    assert invoke(session).status_code == 409


def test_unexpected_tool_call_is_never_executed(session, monkeypatch):
    async def stream(*args):
        yield {
            "type": "turn",
            "message": {
                "content": "saved",
                "tool_calls": [{"function": {"name": "record_expense"}}],
            },
        }

    monkeypatch.setattr(provider, "stream_turn", stream)
    assert invoke(session).status_code == 503
