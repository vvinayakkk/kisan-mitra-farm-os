import math
from datetime import UTC, date, datetime

import httpx
import pytest

from skyview.data.v3.ingestion import (
    fetch_mandi,
    fetch_weather,
    mock_values,
    parse_mandi,
    parse_open_meteo,
    parse_power,
)


def meteo():
    return {
        "daily_units": {
            "temperature_2m_min": "°C",
            "temperature_2m_max": "°C",
            "precipitation_sum": "mm",
        },
        "daily": {
            "time": ["2026-10-14", "2026-10-15"],
            "temperature_2m_min": [20, None],
            "temperature_2m_max": [30, 29],
            "precipitation_sum": [0, 4],
        },
    }


def test_weather_missing_is_not_zero():
    rows = parse_open_meteo(meteo())
    assert rows[1]["temperature_min_c"] is None
    assert rows[0]["rainfall_mm"] == 0


@pytest.mark.parametrize("kind", ["unit", "length", "reversed", "nan"])
def test_weather_bad_inputs(kind):
    payload = meteo()
    if kind == "unit":
        payload["daily_units"]["precipitation_sum"] = "inch"
    if kind == "length":
        payload["daily"]["temperature_2m_min"] = []
    if kind == "reversed":
        payload["daily"]["temperature_2m_min"][0] = 40
    if kind == "nan":
        payload["daily"]["temperature_2m_min"][0] = float("nan")
    with pytest.raises(ValueError):
        parse_open_meteo(payload)


def test_power_fill_values_and_units():
    payload = {
        "properties": {
            "parameter": {
                "T2M_MIN": {"20261001": -999},
                "T2M_MAX": {"20261001": 30},
                "PRECTOTCORR": {"20261001": 2},
                "RH2M": {"20261001": 60},
            }
        },
        "parameters": {
            k: {"units": u}
            for k, u in {
                "T2M_MIN": "C",
                "T2M_MAX": "C",
                "PRECTOTCORR": "mm/day",
                "RH2M": "%",
            }.items()
        },
    }
    assert parse_power(payload)[0]["temperature_min_c"] is None
    payload["parameters"]["RH2M"]["units"] = "fraction"
    with pytest.raises(ValueError):
        parse_power(payload)


def test_market_quarantines_future_units_bad_bands():
    record = {
        "state": "Punjab",
        "market": "Test",
        "commodity": "Wheat",
        "arrival_date": "14/10/2026",
        "min_price": "1000",
        "modal_price": "1100",
        "max_price": "1200",
    }
    rows, bad = parse_mandi(
        {
            "records": [
                record,
                {**record, "unit": "Rs/100Nuts"},
                {**record, "arrival_date": "15/10/2026"},
                {**record, "modal_price": "1300"},
            ]
        },
        date(2026, 10, 14),
    )
    assert len(rows) == 1 and len(bad) == 3
    assert rows[0]["modal_price"] == 1100


def test_mock_bounded_smooth_deterministic():
    now = datetime(2026, 10, 14, 12, tzinfo=UTC)
    first = mock_values("station", now)
    second = mock_values(
        "station", datetime(2026, 10, 14, 12, 0, 5, tzinfo=UTC)
    )
    assert first == mock_values("station", now)
    assert 0 <= first["humidity_pct"] <= 100 and 0 <= first["soil_moisture_pct"] <= 100
    assert abs(first["temperature_c"] - second["temperature_c"]) < 0.1
    assert all(math.isfinite(x) for x in first.values())


def test_credentials_never_in_ogd_errors():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, json={"error": "bad"})
        )
    )
    with pytest.raises(RuntimeError) as error:
        fetch_mandi("super-secret-key", client=client)
    assert "super-secret-key" not in str(error.value)


def test_forecast_transport_request_and_bounds():
    def handle(request):
        assert request.url.params["forecast_days"] == "16"
        assert request.url.params["timezone"] == "UTC"
        return httpx.Response(200, json=meteo())

    assert (
        len(
            fetch_weather(
                28.61, 77.21, client=httpx.Client(transport=httpx.MockTransport(handle))
            )["daily"]["time"]
        )
        == 2
    )


def test_live_mock_worker_refuses(monkeypatch):
    from skyview.data.v3.ingestion import mock_once

    monkeypatch.setenv("SKYVIEW_DATA_MODE", "v3_live")
    with pytest.raises(RuntimeError, match="disabled"):
        mock_once()


def test_mandi_cursor_pages_resume_and_finish():
    offsets = []

    def handle(request):
        offsets.append(int(request.url.params["offset"]))
        count = 1000 if len(offsets) == 1 else 2
        return httpx.Response(200, json={"records": [{"commodity": "Wheat"}] * count})

    client = httpx.Client(transport=httpx.MockTransport(handle))
    first = fetch_mandi("secret", client=client, max_pages=1, offset=3000)
    assert first["complete"] is False and first["next_offset"] == 4000
    last = fetch_mandi(
        "secret", client=client, max_pages=1, offset=first["next_offset"]
    )
    assert last["complete"] is True and last["next_offset"] == 0
    assert offsets == [3000, 4000]


def test_mandi_transient_retry_is_bounded_and_credentials_safe(monkeypatch):
    monkeypatch.setattr("skyview.data.v3.ingestion.time.sleep", lambda _: None)
    attempts = []

    def transient(request):
        attempts.append(1)
        return httpx.Response(503 if len(attempts) < 3 else 200, json={"records": []})

    assert fetch_mandi(
        "secret", client=httpx.Client(transport=httpx.MockTransport(transient))
    )["complete"]
    assert len(attempts) == 3

    def unavailable(request):
        raise httpx.ConnectError(str(request.url), request=request)

    with pytest.raises(RuntimeError) as error:
        fetch_mandi(
            "do-not-leak",
            client=httpx.Client(transport=httpx.MockTransport(unavailable)),
        )
    assert "do-not-leak" not in str(error.value)


def test_mandi_rejects_malformed_payload_before_advancing():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"records": "bad"})
        )
    )
    with pytest.raises(ValueError):
        fetch_mandi("secret", client=client)
