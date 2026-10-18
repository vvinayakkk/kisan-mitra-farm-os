import base64
import io
import json
import wave
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from skyview.api import v3_voice_routes as voice


def wav(seconds=1):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 16000 * seconds)
    return output.getvalue()


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(voice.router)
    app.dependency_overrides[voice.identity] = lambda: "fixture-farmer"
    monkeypatch.setattr(
        voice,
        "get_settings",
        lambda: SimpleNamespace(
            SARVAM_AI_API_KEY="test-key-not-real", GROQ_API_KEYS=[]
        ),
    )
    return TestClient(app)


def test_requires_server_capability_before_provider(monkeypatch):
    app = FastAPI()
    app.include_router(voice.router)
    assert (
        TestClient(app)
        .post("/api/speech/synthesize", json={"text": "Hello"})
        .status_code
        == 401
    )


def test_rejects_invalid_audio_without_fabricated_transcript(client):
    r = client.post(
        "/api/speech/transcribe",
        files={"file": ("fake.wav", b"not audio", "audio/wav")},
    )
    assert r.status_code == 400
    assert "Raju" not in r.text


def test_rejects_oversized_audio(client):
    r = client.post(
        "/api/speech/transcribe",
        files={"file": ("large.wav", b"x" * (voice.AUDIO_LIMIT + 1), "audio/wav")},
    )
    assert r.status_code == 413


def test_rejects_long_wav_before_provider(client):
    r = client.post(
        "/api/speech/transcribe", files={"file": ("long.wav", wav(31), "audio/wav")}
    )
    assert r.status_code == 400


def test_missing_providers_fail_without_filling_fields(client, monkeypatch):
    monkeypatch.setattr(
        voice,
        "get_settings",
        lambda: SimpleNamespace(SARVAM_AI_API_KEY=None, GROQ_API_KEYS=[]),
    )
    r = client.post(
        "/api/voice/process", files={"audio": ("short.wav", wav(), "audio/wav")}
    )
    assert r.status_code == 503
    assert "Nothing was filled in" in r.text


def test_transcribes_actual_provider_text(client, monkeypatch):
    async def provider(*args, **kwargs):
        return {"transcript": "I grow wheat", "language_code": "en-IN"}

    monkeypatch.setattr(voice, "provider_json", provider)
    r = client.post(
        "/api/speech/transcribe",
        files={"file": ("short.wav", wav(), "audio/wav")},
        data={"language_code": "en-IN"},
    )
    assert r.status_code == 200
    assert r.json()["transcript"] == "I grow wheat"
    assert r.json()["mocked"] is False


def test_sarvam_failure_can_use_real_groq_transcription(client, monkeypatch):
    monkeypatch.setattr(
        voice,
        "get_settings",
        lambda: SimpleNamespace(SARVAM_AI_API_KEY=None, GROQ_API_KEYS=["fixture-key"]),
    )

    async def provider(url, **kwargs):
        assert url.endswith("/audio/transcriptions")
        assert kwargs["data"]["model"] == "whisper-large-v3-turbo"
        return {"text": "My field needs a check"}

    monkeypatch.setattr(voice, "provider_json", provider)
    r = client.post(
        "/api/speech/transcribe", files={"file": ("short.wav", wav(), "audio/wav")}
    )
    assert r.json()["source"] == "Groq Whisper transcription"


def test_speech_returns_wav_base64_not_a_fake_empty_audio(client, monkeypatch):
    encoded = base64.b64encode(wav()).decode()

    async def provider(url, **kwargs):
        assert kwargs["json"]["text"] == "Hello farmer"
        assert kwargs["json"]["language_code"] == "en-IN"
        assert "inputs" not in kwargs["json"]
        return {"audios": [encoded]}

    monkeypatch.setattr(voice, "provider_json", provider)
    r = client.post(
        "/api/speech/synthesize", json={"text": "Hello farmer", "language": "en-IN"}
    )
    assert r.status_code == 200
    assert base64.b64decode(r.json()["audio"])[:4] == b"RIFF"


def test_invalid_provider_audio_is_unavailable(client, monkeypatch):
    async def provider(*args, **kwargs):
        return {"audios": ["not-base64"]}

    monkeypatch.setattr(voice, "provider_json", provider)
    assert (
        client.post("/api/speech/synthesize", json={"text": "Hello"}).status_code == 503
    )


@pytest.mark.parametrize(
    "payload", [{"text": "x" * 2501}, {"text": "hello", "language": "not-a-language"}]
)
def test_speech_request_bounds(client, payload):
    assert client.post("/api/speech/synthesize", json=payload).status_code == 422


def test_translation_preserves_exact_item_mapping(client, monkeypatch):
    async def provider(*args, **kwargs):
        return {"translated_text": "अनुवाद " + kwargs["json"]["input"]}

    monkeypatch.setattr(voice, "provider_json", provider)
    r = client.post(
        "/api/translate", json={"texts": ["Soil", "Rain"], "target_language": "hi-IN"}
    )
    assert r.status_code == 200
    assert r.json()["translations"] == {"Soil": "अनुवाद Soil", "Rain": "अनुवाद Rain"}


def test_translation_is_never_mocked_when_unavailable(client, monkeypatch):
    monkeypatch.setattr(
        voice,
        "get_settings",
        lambda: SimpleNamespace(SARVAM_AI_API_KEY=None, GROQ_API_KEYS=[]),
    )
    assert client.post("/api/translate", json={"text": "Rain"}).status_code == 503


def test_voice_extraction_drops_ownership_and_does_not_save(client, monkeypatch):
    async def model(*args, **kwargs):
        return json.dumps(
            {
                "name": "Demo farmer",
                "crops": ["Wheat"],
                "phone": "private",
                "farmer_id": "other",
                "approval": True,
            }
        )

    monkeypatch.setattr(voice, "completion", model)
    r = client.post(
        "/api/profile/voice-update", json={"transcript": "Demo farmer grows wheat"}
    )
    assert r.status_code == 200
    assert r.json()["identified_fields"] == {"name": "Demo farmer", "crops": ["Wheat"]}
    assert r.json()["saved"] is False
    assert r.json()["requires_review"] is True


def test_voice_agent_ignores_payload_phone_and_streams_real_progress(
    client, monkeypatch
):
    seen = []
    monkeypatch.setattr(
        voice.repo,
        "profile",
        lambda owner: (
            seen.append(owner)
            or {
                "profile": {
                    "crops": ["Wheat"],
                    "state": "Punjab",
                    "data_origin": "synthetic",
                }
            }
        ),
    )
    monkeypatch.setattr(
        voice.repo,
        "station_snapshot",
        lambda owner, station: seen.append(owner) or {"available": False},
    )

    async def model(messages, **kwargs):
        assert "synthetic" in messages[-1]["content"]
        assert "arbitrary-phone" not in messages[-1]["content"]
        return "Demo farm information only. Open chat to make changes."

    monkeypatch.setattr(voice, "completion", model)
    r = client.post(
        "/api/voice/agent",
        json={
            "message": "How is my farm?",
            "phone": "arbitrary-phone",
            "language": "en-IN",
        },
    )
    events = [json.loads(line) for line in r.text.splitlines()]
    assert events[0]["type"] == "step"
    assert events[-1]["type"] == "done"
    assert events[-1]["actions_performed"] == []
    assert seen == ["fixture-farmer", "fixture-farmer"]


def test_forged_capability_headers_are_rejected(monkeypatch):
    from skyview.assistant import store

    monkeypatch.setattr(store, "authenticate", lambda *args: False)
    app = FastAPI()
    app.include_router(voice.router)
    response = TestClient(app).post(
        "/api/speech/synthesize",
        json={"text": "Hello"},
        headers={
            "Authorization": "Bearer forged",
            "X-Assistant-Session": "a" * 32,
            "X-Farmer-ID": "other-owner",
        },
    )
    assert response.status_code == 401


def test_voice_write_requests_do_not_run_model_or_actions(client, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Model should not run a write request")

    monkeypatch.setattr(voice, "completion", forbidden)
    response = client.post(
        "/api/voice/agent",
        json={
            "message": "Delete my farm task",
            "language": "en-IN",
            "stream_steps": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["actions_performed"] == []
    assert "No action was performed" in response.json()["response"]


def test_capabilities_report_actual_configuration_without_keys(client):
    response = client.get("/api/speech/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["transcription_available"] is True
    assert body["playback_available"] is True
    assert body["transcription_mode"] == "completed_recording"
    assert body["audio_stored_by_application"] is False
    assert body["conversation_available"] is True
    assert body["conversation_mode"] == "automatic_speech_turns"
    assert body["conversation_agent"] == "/api/assistant/sessions/{sid}/run"
    assert "approval" in body["write_review"]
    assert "test-key-not-real" not in response.text


def test_capabilities_disabled_without_provider(client, monkeypatch):
    monkeypatch.setattr(
        voice,
        "get_settings",
        lambda: SimpleNamespace(SARVAM_AI_API_KEY=None, GROQ_API_KEYS=[]),
    )
    body = client.get("/api/speech/capabilities").json()
    assert body["transcription_available"] is False
    assert body["playback_available"] is False
    assert body["conversation_available"] is False


def test_truncated_wav_rejected_before_provider(client, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Incomplete audio must not reach provider")

    monkeypatch.setattr(voice, "provider_json", forbidden)
    response = client.post(
        "/api/speech/transcribe",
        files={"file": ("partial.wav", wav()[:-100], "audio/wav")},
    )
    assert response.status_code == 400
    assert "incomplete" in response.text


def test_transcription_is_reviewable_and_never_saved(client, monkeypatch):
    async def provider(*args, **kwargs):
        return {"transcript": "Spend 500 rupees on seeds", "language_code": "en-IN"}

    monkeypatch.setattr(voice, "provider_json", provider)
    response = client.post(
        "/api/speech/transcribe",
        files={"file": ("short.wav", wav(), "audio/wav")},
        data={"language_code": "en-IN"},
    )
    assert response.json()["requires_review"] is True
    assert response.json()["saved"] is False
    assert response.json()["transcription_mode"] == "completed_recording"


@pytest.mark.asyncio
async def test_gemini_only_deployment_supports_voice_completion(monkeypatch):
    from skyview.utils import llm_pool
    monkeypatch.setattr(voice, 'get_settings', lambda: SimpleNamespace(GROQ_API_KEYS=[], GEMINI_API_KEY='fixture-key', GEMINI_MODEL='fixture-model'))
    async def gemini(messages, **kwargs):
        assert kwargs['model_name']=='fixture-model'
        assert 'JSON object' in messages[-1]['content']
        return '{"name":"Farmer"}'
    monkeypatch.setattr(llm_pool, '_invoke_gemini', gemini)
    assert await voice.completion([{'role':'user','content':'Farm profile'}], json_mode=True)=='{"name":"Farmer"}'
