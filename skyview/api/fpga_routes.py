"""
FPGA Accelerator Routes
POST /api/fpga/fusion
POST /api/fpga/rain-predict
POST /api/fpga/combined-analysis
POST /api/fpga/test
GET  /api/fpga/status
"""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from skyview.agents.fpga_agent import HardwareUnavailable, get_fpga_bridge
from skyview.utils.llm_pool import invoke_llm
from skyview.utils.logger import get_logger

router = APIRouter(prefix="/api/fpga", tags=["FPGA"])
logger = get_logger(__name__)


def _HW_MODE():
    return "real_hardware" if get_fpga_bridge().get_status()["connected"] else "not_connected"


def _connected_bridge():
    bridge = get_fpga_bridge()
    if not bridge.get_status()["connected"]:
        raise HTTPException(503, "FPGA is not connected or has not passed its version probe")
    return bridge


class FusionInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    soil_moisture: float = Field(50.0, ge=0, le=100)
    temperature: float = Field(25.0, ge=0, le=100)
    humidity: float = Field(60.0, ge=0, le=100)
    light_level: float = Field(70.0, ge=0, le=100)
    user_id: str | None = None


class RainInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    temperature: float = 25.0
    humidity: float = 60.0
    pressure: float = 1013.0
    wind_speed: float = 5.0
    station_id: str = "WS01"


class CombinedInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    soil_moisture: float = 50.0
    temperature: float = 25.0
    humidity: float = 60.0
    light_level: float = 70.0
    station_id: str = "WS01"
    user_id: str | None = None


def _json_object(content: str | None) -> dict:
    if not content:
        return {}
    payload = content.strip()
    if payload.startswith("```"):
        payload = payload.split("\n", 1)[-1]
        payload = payload.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def _llm_validate_fusion(raw: dict, inputs: FusionInput) -> dict:
    prompt = (
        f"FPGA Sensor Fusion raw output: {json.dumps(raw)}\n"
        f"Actual readings: Soil={inputs.soil_moisture}%, Temp={inputs.temperature}°C, "
        f"Humidity={inputs.humidity}%, Light={inputs.light_level}%\n"
        "Cross-validate and reply with JSON only: "
        '{"adjusted_fusion_score":<0-100>,"adjusted_stress_index":<0-100>,'
        '"adjusted_alert_level":<0-3>,"alert_name":"<Normal/Moderate/High/Critical>",'
        '"assessment":"<2 sentences>","recommendations":["<tip1>","<tip2>","<tip3>"]}'
    )
    content = await invoke_llm([("user", prompt)], temperature=0.1, timeout=12)
    return _json_object(content)


async def _llm_validate_rain(raw: dict, inputs: RainInput) -> dict:
    prompt = (
        f"FPGA Rain Prediction raw: {json.dumps(raw)}\n"
        f"Actual: Temp={inputs.temperature}°C, Humidity={inputs.humidity}%, "
        f"Pressure={inputs.pressure} hPa, Wind={inputs.wind_speed} km/h\n"
        "Cross-validate and reply with JSON only: "
        '{"adjusted_rain_probability":<0-100>,"adjusted_stress_level":<0-100>,'
        '"rain_alert":<0or1>,"confidence":"<high/medium/low>",'
        '"recommendation":"<2 sentences>","reasoning":"<1 sentence>"}'
    )
    content = await invoke_llm([("user", prompt)], temperature=0.1, timeout=12)
    return _json_object(content)


@router.get("/status")
def fpga_status():
    bridge = get_fpga_bridge()
    return {
        "status": "ok",
        "hardware_mode": _HW_MODE(),
        "fpga_status": bridge.get_status(),
        "physical_hardware_confirmed": bridge.get_status()["connected"],
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/fusion")
async def sensor_fusion(data: FusionInput):
    bridge = _connected_bridge()
    try:
        raw = bridge.send_fusion(
            data.soil_moisture,
            data.temperature,
            data.humidity,
            data.light_level,
        )
    except (HardwareUnavailable, ValueError, OSError) as exc:
        raise HTTPException(503, str(exc)) from exc
    adjusted = await _llm_validate_fusion(raw, data)
    final = raw
    return {
        "status": "success",
        "hardware_mode": _HW_MODE(),
        "fpga_result": final,
        "fpga_raw": raw,
        "ai_insights": adjusted.get("assessment", ""),
        "ai_recommendations": adjusted.get("recommendations", []),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/rain-predict")
async def rain_predict(data: RainInput):
    bridge = _connected_bridge()
    try:
        raw = bridge.send_rain_prediction(
            data.temperature, data.humidity, data.pressure, data.wind_speed
        )
    except (HardwareUnavailable, ValueError, OSError) as exc:
        raise HTTPException(503, str(exc)) from exc
    adjusted = await _llm_validate_rain(raw, data)
    final = raw
    return {
        "status": "success",
        "hardware_mode": _HW_MODE(),
        "prediction": final,
        "fpga_raw": raw,
        "farmer_recommendation": adjusted.get("recommendation", ""),
        "ai_reasoning": adjusted.get("reasoning", ""),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/combined-analysis")
async def combined_analysis(data: CombinedInput):
    fusion_data = FusionInput(
        soil_moisture=data.soil_moisture,
        temperature=data.temperature,
        humidity=data.humidity,
        light_level=data.light_level,
        user_id=data.user_id,
    )
    rain_data = RainInput(
        temperature=data.temperature,
        humidity=data.humidity,
        pressure=1013.0,
        wind_speed=5.0,
        station_id=data.station_id,
    )
    f_resp = await sensor_fusion(fusion_data)
    r_resp = await rain_predict(rain_data)

    fs = f_resp.get("fpga_result", {})
    rp = r_resp.get("prediction", {})

    prompt = (
        f"Farm results: Fusion={fs.get('fusion_score')}/100, "
        f"Stress={fs.get('stress_index')}%, Rain={rp.get('rain_probability')}%. "
        f"Sensor: Temp={data.temperature}°C, Soil={data.soil_moisture}%, "
        f"Humidity={data.humidity}%. "
        'Reply JSON: {"overall_risk":"<low/moderate/high/critical>",'
        '"recommendation":"<2-3 sentences>","actions":["<a1>","<a2>","<a3>"]}'
    )
    rec_raw = await invoke_llm([("user", prompt)], temperature=0.2, timeout=12)
    rec = _json_object(rec_raw)

    return {
        "status": "success",
        "hardware_mode": _HW_MODE(),
        "sensor_fusion": fs,
        "rain_prediction": rp,
        "combined_analysis": {
            "overall_risk_level": rec.get("overall_risk", "low"),
            "recommendation": rec.get("recommendation", ""),
            "actions": rec.get("actions", []),
        },
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/test")
async def fpga_test():
    bridge = _connected_bridge()
    cases = [
        {"name": "Optimal", "soil": 50, "temp": 25, "humid": 60, "light": 70},
        {"name": "Dry Soil", "soil": 10, "temp": 30, "humid": 40, "light": 80},
        {"name": "Hot", "soil": 60, "temp": 40, "humid": 30, "light": 90},
        {"name": "Frost Risk", "soil": 50, "temp": 2, "humid": 80, "light": 30},
    ]
    try:
        results = [
            {
                "test": c["name"],
                "input": c,
                "output": bridge.send_fusion(c["soil"], c["temp"], c["humid"], c["light"]),
            }
            for c in cases
        ]
    except (HardwareUnavailable, ValueError, OSError) as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"status": "success", "tests": results, "hardware_mode": _HW_MODE()}
