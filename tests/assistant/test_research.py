import asyncio
from types import SimpleNamespace

import httpx
import pytest

from skyview.assistant import research
from skyview.assistant.tools import Executor, public_catalog, schemas


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(
        research,
        "get_settings",
        lambda: SimpleNamespace(
            GEMINI_API_KEY="private-test-key",
            GEMINI_MODEL="gemini-2.5-flash",
        ),
    )


def grounded(text="Check the official scheme conditions."):
    return {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": text}]},
                "groundingMetadata": {
                    "groundingChunks": [
                        {"web": {"uri": "https://pmkisan.gov.in/", "title": "PM-KISAN"}}
                    ],
                    "groundingSupports": [
                        {"segment": {"text": text}, "groundingChunkIndices": [0]}
                    ],
                    "webSearchQueries": ["PM KISAN official conditions"],
                    "searchEntryPoint": {
                        "renderedContent": "<div>Google suggestions</div>"
                    },
                },
            }
        ]
    }


def run_request(handler, query="PM KISAN conditions", language="en"):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await research.research(query, language, client=client)

    return asyncio.run(run())


def test_grounding_request_returns_source_evidence_and_language():
    def handler(request):
        assert "private-test-key" not in str(request.url)
        assert request.headers["x-goog-api-key"] == "private-test-key"
        import json

        body = json.loads(request.content)
        assert body["tools"] == [{"google_search": {}}]
        assert "Hindi" in body["systemInstruction"]["parts"][0]["text"]
        return httpx.Response(200, json=grounded("आधिकारिक नियम देखें।"))

    result = run_request(handler, language="hi-IN")
    assert result["available"] is True
    assert result["status"] == "grounded"
    assert result["language"] == "hi"
    assert result["retrieved_at"]
    assert result["sources"] == [
        {"id": 1, "title": "PM-KISAN", "url": "https://pmkisan.gov.in/"}
    ]
    assert result["evidence"] == [{"text": "आधिकारिक नियम देखें।", "source_ids": [1]}]
    assert result["search_queries"] == ["PM KISAN official conditions"]
    assert result["search_suggestions_html"] == "<div>Google suggestions</div>"


def test_missing_key_never_contacts_provider(monkeypatch):
    monkeypatch.setattr(
        research, "get_settings", lambda: SimpleNamespace(GEMINI_API_KEY=None)
    )

    def handler(request):
        pytest.fail("A request was sent without a key")

    result = run_request(handler)
    assert result["status"] == "not_configured"
    assert result["available"] is False and result["answer"] == ""


def test_timeout_hides_provider_exception():
    def handler(request):
        raise httpx.ReadTimeout(
            "private-test-key secret provider body", request=request
        )

    result = run_request(handler)
    assert result["status"] == "timeout" and not result["available"]
    assert "private-test-key" not in str(result)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"candidates": []},
        {"candidates": [None]},
        {"candidates": [{"content": "invalid"}]},
        {"candidates": [{"content": {"parts": None}}]},
    ],
)
def test_malformed_response_has_no_fabricated_fallback(payload):
    result = run_request(lambda request: httpx.Response(200, json=payload))
    assert not result["available"]
    assert result["sources"] == [] and result["answer"] == ""


def test_non_json_and_provider_errors_are_explicit():
    result = run_request(lambda request: httpx.Response(200, content="not json"))
    assert result["status"] == "provider_unavailable"
    result = run_request(lambda request: httpx.Response(429, text="private-test-key"))
    assert result["status"] == "quota_exceeded"
    assert "private-test-key" not in str(result)


def test_source_less_answer_is_not_claimed_as_research():
    payload = grounded()
    payload["candidates"][0].pop("groundingMetadata")
    result = run_request(lambda request: httpx.Response(200, json=payload))
    assert result["status"] == "ungrounded" and result["answer"] == ""


def test_sources_without_matching_evidence_are_not_claimed_as_research():
    payload = grounded()
    payload["candidates"][0]["groundingMetadata"]["groundingSupports"][0]["segment"][
        "text"
    ] = "An invented claim."
    result = run_request(lambda request: httpx.Response(200, json=payload))
    assert result["status"] == "ungrounded"


def test_deduplicates_sources_and_rejects_unsafe_urls():
    payload = grounded()
    meta = payload["candidates"][0]["groundingMetadata"]
    meta["groundingChunks"] += [
        {"web": {"uri": "javascript:alert(1)"}},
        {"web": {"uri": "https://pmkisan.gov.in/"}},
        {"web": {"uri": "https://secret@evil.example/"}},
    ]
    meta["groundingSupports"][0]["groundingChunkIndices"] = [
        0,
        1,
        2,
        3,
        999,
        -1,
        True,
        "0",
    ]
    result = research.parse_grounded_response(payload, "conditions", "en")
    assert len(result["sources"]) == 1
    assert result["evidence"][0]["source_ids"] == [1]


def test_large_response_and_truncated_generation_are_rejected():
    result = run_request(
        lambda request: httpx.Response(
            200, content=b"x" * (research.MAX_RESPONSE_BYTES + 1)
        )
    )
    assert result["status"] == "invalid_response"
    payload = grounded()
    payload["candidates"][0]["finishReason"] = "MAX_TOKENS"
    assert not research.parse_grounded_response(payload, "conditions", "en")[
        "available"
    ]


def test_core_tool_and_skill_are_available_without_loading():
    assert "web_research" in {tool["function"]["name"] for tool in schemas([])}
    catalog = public_catalog()
    assert any(skill["id"] == "web-research" for skill in catalog["skills"])
    assert (
        next(tool for tool in catalog["tools"] if tool["id"] == "web_research")[
            "approval"
        ]
        is False
    )


def test_executor_routes_and_caches_research(monkeypatch):
    calls = []

    async def fake(query, language, *, client):
        calls.append((query, language, client))
        return {"available": True, "sources": []}

    monkeypatch.setattr(research, "research", fake)
    executor = Executor("test-session", "WS01", "shared-http-client")

    async def run():
        await executor.run(
            "web_research", {"query": "Wheat research", "language": "mr"}
        )
        await executor.run(
            "web_research", {"query": "Wheat research", "language": "mr"}
        )

    asyncio.run(run())
    assert calls == [("Wheat research", "mr", "shared-http-client")]


def test_hard_deadline_covers_slow_provider(monkeypatch):
    monkeypatch.setattr(research, "TIMEOUT_SECONDS", 0.01)

    async def handler(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json=grounded())

    assert run_request(handler)["status"] == "timeout"


def test_cancellation_is_not_swallowed():
    async def handler(request):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        run_request(handler)


@pytest.mark.parametrize("query", ["", "   ", "x" * 1201])
def test_invalid_queries_never_call_provider(query):
    with pytest.raises(ValueError):
        run_request(
            lambda request: pytest.fail("Provider contacted for invalid query"),
            query=query,
        )
