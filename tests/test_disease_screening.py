import base64
import io
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from skyview.agents import disease_service as service
from skyview.api import disease_routes as routes


def photo(size=(160, 80), fmt="PNG"):
    output = io.BytesIO()
    Image.new("RGB", size, "green").save(output, format=fmt)
    return output.getvalue()


def diagnostic(**changes):
    return {
        "disease_name": "Possible leaf spot",
        "crop_identified": "Rice",
        "confidence": 75,
        "severity": "Moderate",
        "description": "Visible spots need a field check.",
        "bounding_boxes": [],
        "solutions": [],
        "symptoms": ["Spots"],
        **changes,
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "legacy")
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


@pytest.mark.parametrize(
    "content", [b"", b"<svg><script>fake()</script></svg>", b"Not a photo"]
)
def test_invalid_photos_do_not_reach_a_provider(content):
    with pytest.raises(ValueError):
        service.normalize_image(content)


def test_image_aspect_ratio_is_preserved_and_metadata_not_sent():
    output = service.normalize_image(photo((1800, 900)))
    with Image.open(io.BytesIO(output)) as image:
        assert image.size == (1024, 512)
        assert image.getexif() == {}


def test_oversized_upload_and_tiny_image_rejected():
    with pytest.raises(ValueError, match="5 MB"):
        service.normalize_image(b"x" * (service.MAX_IMAGE_BYTES + 1))
    with pytest.raises(ValueError, match="too small"):
        service.normalize_image(photo((8, 8)))


def test_low_confidence_never_prescribes_a_treatment():
    value = service._result(
        diagnostic(
            confidence=22,
            solutions=[{"title": "Spray", "details": "Fake dose", "type": "Chemical"}],
        ),
        "test",
        "fixture",
    )
    assert value["disease_name"].startswith("Unknown")
    assert value["solutions"] == []
    assert value["requires_confirmation"] is True
    assert "not measured" in value["confidence_note"]


def test_provider_chemical_advice_is_not_forwarded():
    value = service._result(
        diagnostic(
            solutions=[
                {
                    "title": "Spray",
                    "details": "Not a registered label",
                    "type": "Chemical",
                }
            ]
        ),
        "test",
        "fixture",
    )
    assert value["solutions"] == []


def test_healthy_label_is_limited_to_visible_evidence():
    value = service._result(
        diagnostic(disease_name="Healthy", confidence=99), "test", "fixture"
    )
    assert value["disease_name"] == "No clear disease symptoms visible in this photo"
    assert value["requires_confirmation"] is True


def test_boxes_clamp_without_fabricating_a_minimum_area():
    value = service._result(
        diagnostic(
            bounding_boxes=[
                {"x": -10, "y": 90, "width": 200, "height": 30},
                {"x": 20, "y": 20, "width": -5, "height": 2},
            ]
        ),
        "test",
        "fixture",
    )
    assert value["bounding_boxes"] == [{"x": 0, "y": 90, "width": 100, "height": 10}]


@pytest.mark.parametrize("confidence", [float("nan"), float("inf"), 101, -1])
def test_invalid_provider_certainty_is_rejected(confidence):
    with pytest.raises(ValueError):
        service._result(diagnostic(confidence=confidence), "test", "fixture")


@pytest.mark.asyncio
async def test_actual_provider_result_parsed_and_image_hash_added(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(GROQ_API_KEYS=["test-not-a-key"], GEMINI_API_KEY=""),
    )
    calls = []

    class Provider:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            calls.append(kwargs["json"])
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": json.dumps(diagnostic())}}]},
            )

    monkeypatch.setattr(service.httpx, "AsyncClient", Provider)
    value = await service.analyze_crop_image(photo(), "rice")
    assert value["analysis_source"] == "Groq crop vision"
    assert len(value["image_hash"]) == 64
    assert calls[0]["model"] == "qwen/qwen3.8-27b"
    assert "unverified" in calls[0]["messages"][0]["content"][0]["text"]


@pytest.mark.asyncio
async def test_no_configured_provider_fails_honestly(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(GROQ_API_KEYS=[], GEMINI_API_KEY=""),
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="No diagnosis was made"):
        await service.analyze_crop_image(photo())


@pytest.mark.parametrize(
    "payload",
    ["not base64!", "data:text/html;base64,PHNjcmlwdD4=", "data:image/png;base64,?"],
)
def test_bad_base64_is_client_error(client, payload):
    response = client.post("/api/disease/detect-base64", json={"image_base64": payload})
    assert response.status_code == 400
    assert "engine failure" not in response.text


def test_multipart_reads_bounded_bytes_and_returns_413(client):
    response = client.post(
        "/disease/detect",
        files={
            "image": ("large.jpg", b"x" * (service.MAX_IMAGE_BYTES + 1), "image/jpeg")
        },
    )
    assert response.status_code == 413


def test_invalid_image_returns_400_not_500(client):
    response = client.post(
        "/disease/detect", files={"image": ("bad.jpg", b"not image", "image/jpeg")}
    )
    assert response.status_code == 400


def test_provider_failure_is_503_without_secrets(client, monkeypatch):
    async def unavailable(*args, **kwargs):
        raise RuntimeError("Crop vision is unavailable. No diagnosis was made.")

    monkeypatch.setattr(routes, "analyze_crop_image", unavailable)
    response = client.post(
        "/disease/detect", files={"image": ("leaf.png", photo(), "image/png")}
    )
    assert response.status_code == 503
    assert "No diagnosis was made" in response.text


def test_unexpected_error_does_not_expose_internals(client, monkeypatch):
    async def unavailable(*args, **kwargs):
        raise ArithmeticError("postgresql://secret:password@private-host")

    monkeypatch.setattr(routes, "analyze_crop_image", unavailable)
    response = client.post(
        "/disease/detect-base64",
        json={"image_base64": base64.b64encode(photo()).decode()},
    )
    assert response.status_code == 503
    assert "password" not in response.text


def test_v3_photo_requires_capability_before_provider(client, monkeypatch):
    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_demo")
    response = client.post(
        "/disease/detect", files={"image": ("leaf.png", photo(), "image/png")}
    )
    assert response.status_code == 401


def test_v3_owned_screening_persists_case(client, monkeypatch):
    monkeypatch.setattr(routes, "_owner", lambda *args: "trusted-farmer")

    async def screen(*args, **kwargs):
        return diagnostic()

    saved = []

    def persist(sid, content, assessment, **kwargs):
        saved.append((sid, content, assessment, kwargs))
        return {
            "saved": True,
            "case_id": "case-fixture",
            "status": "needs_expert_review",
        }

    monkeypatch.setattr(routes, "analyze_crop_image", screen)
    monkeypatch.setattr(routes, "persist_crop_assessment", persist)
    response = client.post(
        "/disease/detect",
        files={"image": ("leaf.png", photo(), "image/png")},
        headers={
            "Authorization": "Bearer fixture",
            "X-Assistant-Session": "trusted-session",
        },
    )
    assert response.status_code == 200
    assert response.json()["case"]["saved"] is True
    assert saved[0][0] == "trusted-session"
    assert saved[0][3]["crop_cycle_id"] is None
