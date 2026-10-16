import pytest
from pydantic import ValidationError

from skyview.assistant import engine, models, store
from skyview.languages import LANGUAGE_NAMES, normalize_language, speech_language


@pytest.mark.parametrize("code", list(LANGUAGE_NAMES))
def test_chat_accepts_every_supported_profile_language(code):
    assert models.RunRequest(language=code).language == code


def test_locale_and_odia_aliases_are_canonical():
    assert normalize_language("te-IN") == "te"
    assert models.RunRequest(language="od-IN").language == "or"
    assert speech_language("or") == "od-IN"
    with pytest.raises(ValidationError):
        models.RunRequest(language="invented")


def test_compact_schemas_preserve_fields_named_title_and_defaults_are_server_owned():
    from skyview.assistant.provider import inline_schema

    schema = {
        "type": "object",
        "title": "Request",
        "properties": {
            "title": {"type": "string", "title": "Title", "minLength": 1},
            "default": {"type": "boolean", "default": False},
        },
        "required": ["title"],
    }
    compact = inline_schema(schema)
    assert compact["properties"]["title"] == {"type": "string", "minLength": 1}
    assert compact["properties"]["default"] == {"type": "boolean"}
    assert compact["required"] == ["title"]
    assert "title" not in compact


def test_tools_load_by_skill_without_losing_any_capability():
    from skyview.assistant.tools import CORE_TOOLS, SKILL_TOOLS, SKILLS, TOOLS, schemas

    assert set(SKILL_TOOLS) == set(SKILLS)
    assert CORE_TOOLS.union(*SKILL_TOOLS.values()) == set(TOOLS)
    assert {t["function"]["name"] for t in schemas([])} == CORE_TOOLS
    names = {t["function"]["name"] for t in schemas(["documents"])}
    assert "create_file" in names and "market_trend" not in names
    names = {
        t["function"]["name"]
        for t in schemas(["documents", "field-check", "irrigation", "market-prices"])
    }
    assert "create_file" not in names and "market_trend" in names


def test_price_history_cannot_overflow_every_new_chat_prompt(monkeypatch):
    import json

    observation = {
        "tool": "market_trend",
        "arguments": {"commodity": "Rice"},
        "checked_at": "2026-10-15",
        "result": {
            "records": [{"price": 1000}] * 10000,
            "chart": {"points": [1] * 10000},
            "source": "reference",
            "total_observations": 10000,
        },
    }
    monkeypatch.setattr(store, "records", lambda *args: [observation])
    context = engine.observation_context("owned-session")
    assert len(context) < 1000
    assert json.loads(context)[0]["evidence"]["total_observations"] == 10000
    assert "Rice" in context and "Summary only" in context


def test_prompt_uses_owned_profile_when_language_was_not_supplied(
    monkeypatch, tmp_path
):
    from skyview.data.v3 import db, repository

    monkeypatch.setenv("SKYVIEW_DATA_MODE", "legacy")
    monkeypatch.setattr(store, "ROOT", tmp_path)
    sid = store.create_session()["id"]
    monkeypatch.setattr(db, "enabled", lambda: True)
    monkeypatch.setattr(store, "records", lambda *args, **kwargs: [])
    monkeypatch.setattr(engine.attachments, "file_manifest", lambda sid: [])
    monkeypatch.setattr(store, "farmer_id", lambda sid: "owned-farmer")
    monkeypatch.setattr(
        repository, "profile", lambda owner: {"profile": {"preferred_language": "te"}}
    )
    assert "Reply in Telugu" in engine.system_prompt(models.RunRequest(), sid)
    assert "Reply in Marathi" in engine.system_prompt(
        models.RunRequest(language="mr"), sid
    )
