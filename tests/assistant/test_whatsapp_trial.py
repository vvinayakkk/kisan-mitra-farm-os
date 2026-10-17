from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from skyview.api import v3_whatsapp_routes as whatsapp


def test_template_only_trial_does_not_offer_an_agent_connection(monkeypatch):
    monkeypatch.setenv("TWILIO_TRIAL_MODE", "true")
    monkeypatch.setenv("SKYVIEW_PUBLIC_URL", "https://farm.example")
    monkeypatch.setattr(whatsapp.repository, "rows", lambda *_: [])
    monkeypatch.setattr(
        whatsapp,
        "get_settings",
        lambda: SimpleNamespace(
            TWILIO_ACCOUNT_SID="AC" + "a" * 32,
            TWILIO_AUTH_TOKEN="test-token",
            TWILIO_WHATSAPP_NUMBER="+14155550100",
        ),
    )

    channel = whatsapp.channel_summary(object())
    assert channel["trial_limited"] is True
    assert channel["configured"] is False
    assert channel["connected"] is False

    with pytest.raises(HTTPException, match="cannot deliver agent replies"):
        whatsapp.link("farmer-id")
