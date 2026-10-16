import asyncio
import json

import pytest

from skyview.assistant import companion_plans as plans
from skyview.assistant import research


@pytest.fixture
def source():
    return {
        "title": "Review farm records",
        "summary": "Review 2 tasks on 2026-10-15.",
        "steps": [
            {"title": "Inspect wheat", "done": False},
            {"title": "Record the cost", "done": False},
        ],
        "evidence": [
            {"label": "Wheat", "detail": "2026-10-15", "origin": "user_reported"}
        ],
        "research_query": "Wheat seasonal guidance Maharashtra",
    }


def test_translates_only_prose_preserving_evidence_and_structure(monkeypatch, source):
    async def stream(client, messages, tools):
        assert tools == []
        assert "Hindi" in messages[0]["content"]
        assert "evidence" not in messages[1]["content"]
        yield {
            "type": "delta",
            "text": json.dumps(
                {
                    "title": "खेत के रिकॉर्ड देखें",
                    "summary": "2026-10-15 को 2 कार्य देखें।",
                    "steps": ["गेहूं का निरीक्षण करें", "खर्च दर्ज करें"],
                }
            ),
        }

    monkeypatch.setattr(plans.provider, "stream_turn", stream)
    result = asyncio.run(plans.translate_draft(source, "hi"))
    assert result["language"] == "hi" and result["translation_status"] == "translated"
    assert result["title"] == "खेत के रिकॉर्ड देखें"
    assert result["evidence"] == source["evidence"]
    assert result["research_query"] == source["research_query"]
    assert len(result["steps"]) == 2 and all(
        not step["done"] for step in result["steps"]
    )
    assert source["title"] == "Review farm records"


def test_english_skips_provider(monkeypatch, source):
    def no_call(*args):
        pytest.fail("English preparation should need no translation call")

    monkeypatch.setattr(plans.provider, "stream_turn", no_call)
    result = asyncio.run(plans.translate_draft(source, "en"))
    assert result["translation_status"] == "not_needed"


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        json.dumps({"title": "योजना", "summary": "सारांश", "steps": ["केवल एक कार्य"]}),
    ],
)
def test_invalid_translation_preserves_honest_english_fallback(
    monkeypatch, source, payload
):
    async def stream(*args):
        yield {"type": "delta", "text": payload}

    monkeypatch.setattr(plans.provider, "stream_turn", stream)
    result = asyncio.run(plans.translate_draft(source, "hi"))
    assert result["requested_language"] == "hi" and result["language"] == "en"
    assert result["translation_status"] == "unavailable"
    assert all(result[key] == source[key] for key in source)


def test_translation_deadline_preserves_local_plan(monkeypatch, source):
    monkeypatch.setattr(plans, "TRANSLATION_TIMEOUT", 0.01)

    async def stream(*args):
        await asyncio.sleep(1)
        yield {"type": "delta", "text": ""}

    monkeypatch.setattr(plans.provider, "stream_turn", stream)
    result = asyncio.run(plans.translate_draft(source, "mr"))
    assert result["translation_status"] == "unavailable"
    assert result["title"] == source["title"]


def test_research_dedupe_tracks_content_not_retrieval_time(source):
    first = {
        "available": True,
        "answer": "Version one",
        "sources": [{"url": "https://india.gov.in/one"}],
        "retrieved_at": "2026-10-15T00:00:00Z",
    }
    key = plans.proposal_key("schemes", "2026-10-15", source, first)
    assert key == plans.proposal_key(
        "schemes",
        "2026-10-15",
        source,
        {**first, "retrieved_at": "2026-10-15T01:00:00Z"},
    )
    assert key != plans.proposal_key(
        "schemes", "2026-10-15", source, {**first, "answer": "Version two"}
    )
    assert key != plans.proposal_key(
        "schemes",
        "2026-10-15",
        source,
        {**first, "sources": [{"url": "https://india.gov.in/two"}]},
    )


@pytest.mark.parametrize("error", [TimeoutError, RuntimeError])
def test_web_failure_still_completes_local_plan(monkeypatch, source, error):
    job = {"farmer_id": "owner", "area": "markets", "research": True}
    saved = []
    monkeypatch.setattr(plans, "claim", lambda: job)
    monkeypatch.setattr(plans, "snapshot", lambda owner: {"preferred_language": "en"})
    monkeypatch.setattr(plans, "draft", lambda area, context: source)
    monkeypatch.setattr(
        plans, "complete", lambda job, draft, research: saved.append((draft, research))
    )
    monkeypatch.setattr(
        plans,
        "fail",
        lambda job: pytest.fail("Optional web failure must not retry local plan"),
    )

    async def broken(*args):
        raise error("sensitive provider exception")

    monkeypatch.setattr(research, "research", broken)
    assert asyncio.run(plans.process_next()) is True
    assert len(saved) == 1
    assert saved[0][0]["title"] == source["title"]
    assert saved[0][1]["available"] is False
    assert "sensitive" not in str(saved[0][1])


def test_research_cancellation_is_preserved(monkeypatch):
    async def cancelled(*args):
        raise asyncio.CancelledError()

    monkeypatch.setattr(research, "research", cancelled)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(plans.research_for_plan("public query", "en"))
