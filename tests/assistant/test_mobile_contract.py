"""Contracts the Flutter client depends on (mobile/lib/assistant, mobile/lib/core)."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from skyview.api.assistant_routes import authorize
from skyview.assistant import models
from skyview.assistant.engine import display_result
from skyview.assistant.tools import TOOLS, public_catalog


def test_restored_research_keeps_sources_and_bounds_them():
    result = {
        "available": True,
        "answer": "internal synthesis",
        "sources": [{"id": i, "title": f"S{i}", "url": "https://example.gov.in"} for i in range(3)],
        "retrieved_at": "2026-10-17T00:00:00+00:00",
        "search_suggestions_html": "<a href='https://google.com/search?q=x'>x</a>",
        "preparation": {"language": "hi", "translation_status": "translated"},
        "records": ["bulk rows stay in the durable tool result"],
    }
    shown = display_result(result)
    assert [s["title"] for s in shown["sources"]] == ["S0", "S1", "S2"]
    assert shown["retrieved_at"] == result["retrieved_at"]
    assert "search_suggestions_html" in shown
    assert "records" not in shown and "answer" not in shown

    long = display_result({"sources": [{"title": "x" * 9000}]})
    assert len(long["sources"][0]["title"]) == 6000


def test_run_request_never_accepts_a_client_farmer_identity():
    with pytest.raises(ValidationError):
        models.RunRequest(message="hi", farmer_id="someone-else")
    with pytest.raises(ValidationError):
        models.RunRequest(message="hi", user_id="9999999999")


@pytest.mark.parametrize("view", ["assistant", "calendar", "records", "weather"])
def test_mobile_run_views_are_accepted(view):
    assert models.RunRequest(message="hi", workspace_view=view).workspace_view == view


def test_notebook_sub_pages_must_report_as_records():
    # mobile/lib/assistant/suggestions.dart runView() maps these to "records".
    for view in ("ledger", "today", "followups", "missions", "memory", "fields"):
        with pytest.raises(ValidationError):
            models.RunRequest(message="hi", workspace_view=view)


def test_answer_and_approval_fields_are_typed():
    run = models.RunRequest(answers={"crop": "Wheat"}, approval=False, pending_id="p1", language="od-IN")
    assert run.language == "or" and run.approval is False


def test_catalog_marks_every_reviewed_write_for_the_mobile_review_badge():
    catalog = {t["id"]: t for t in public_catalog()["tools"]}
    reviewed = {name for name, tool in TOOLS.items() if tool.approval}
    assert {"save_task", "update_task", "delete_task", "complete_task", "record_expense"} <= reviewed
    assert {k for k, t in catalog.items() if t["approval"]} == reviewed
    assert catalog["market_prices"]["approval"] is False
    assert all(s["name"] and s["description"] for s in public_catalog()["skills"])


@pytest.mark.parametrize(
    "sid,header",
    [
        ("0" * 32, None),
        ("0" * 32, "Token abc"),
        ("not-a-session", "Bearer abc"),
        ("../" + "0" * 29, "Bearer abc"),
    ],
)
def test_private_routes_reject_missing_or_malformed_capabilities(sid, header):
    with pytest.raises(HTTPException) as error:
        authorize(sid, header)
    assert error.value.status_code == 401


def test_speech_routes_require_the_session_identity():
    from skyview.api.v3_routes import identity
    from skyview.api.v3_voice_routes import router

    assert any(d.dependency is identity for d in router.dependencies)


def test_plain_english_instruction_is_not_answered_in_an_earlier_turns_language():
    from skyview.assistant import execution_contract as contract

    messages = [
        {"role": "user", "content": "mere kal ke kaam kya hain? tasks dekh ke batao"},
        {"role": "assistant", "content": "Kal ke liye koi task nahi hai."},
        {"role": "user", "content": "Save a farm task for 2026-10-18: Check soil moisture in North field"},
    ]
    assert "Reply in English" in contract.language_instruction(messages, ui_language="hi")
    messages.append({"role": "user", "content": "kal subah moisture check ka task add karo, mujhe yaad dilana"})
    assert "Hinglish" in contract.language_instruction(messages, ui_language="hi")
