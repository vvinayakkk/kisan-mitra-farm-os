import mmap
import struct
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from skyview.agents.fpga_agent import FPGABridge, HardwareUnavailable
from skyview.api import fpga_routes


def _register_file(tmp_path, version=FPGABridge.VERSION):
    path = tmp_path / "registers.bin"
    path.write_bytes(b"\0" * mmap.PAGESIZE)
    with path.open("r+b") as handle:
        handle.seek(0x24)
        handle.write(struct.pack("<I", version))
    return path


def test_fusion_register_round_trip(tmp_path):
    path = _register_file(tmp_path)
    bridge = FPGABridge(str(path), 0, 100)
    observed = []

    def accelerator():
        with path.open("r+b", buffering=0) as handle:
            while True:
                handle.seek(0)
                if struct.unpack("<I", handle.read(4))[0] == 1:
                    break
                time.sleep(0.001)
            for offset in (0x08, 0x0C, 0x10, 0x14):
                handle.seek(offset)
                observed.append(struct.unpack("<I", handle.read(4))[0])
            for offset, value in ((0x18, 0x3200), (0x1C, 0x1400), (0x20, 7), (0x04, 0x12)):
                handle.seek(offset)
                handle.write(struct.pack("<I", value))

    thread = threading.Thread(target=accelerator)
    thread.start()
    try:
        result = bridge.send_fusion(50, 25, 60, 70)
        assert observed == [50 * 256, 25 * 256, 60 * 256, 70 * 256]
        assert result["fusion_score"] == 50
        assert result["stress_index"] == 20
        assert result["alert_level"] == 1
        assert result["hardware_timestamp_ticks"] == 7
    finally:
        thread.join(timeout=1)
        bridge.close()


def test_fpga_probe_rejects_wrong_ip(tmp_path):
    path = _register_file(tmp_path, version=0)
    with pytest.raises(HardwareUnavailable, match="version mismatch"):
        FPGABridge(str(path), 0)


def test_fusion_timeout_and_input_bounds(tmp_path):
    path = _register_file(tmp_path)
    bridge = FPGABridge(str(path), 0, 5)
    try:
        with pytest.raises(ValueError):
            bridge.send_fusion(101, 25, 60, 70)
        with pytest.raises(ValueError):
            bridge.send_fusion(float("nan"), 25, 60, 70)
        with pytest.raises(HardwareUnavailable, match="timed out"):
            bridge.send_fusion(50, 25, 60, 70)
    finally:
        bridge.close()


def test_api_refuses_unconnected_hardware(monkeypatch):
    from skyview.agents.fpga_agent import DisconnectedBridge

    monkeypatch.setattr(
        fpga_routes, "get_fpga_bridge", lambda: DisconnectedBridge("not connected")
    )
    app = FastAPI()
    app.include_router(fpga_routes.router)
    client = TestClient(app)
    assert client.get("/api/fpga/status").json()["physical_hardware_confirmed"] is False
    assert client.post("/api/fpga/fusion", json={}).status_code == 503
    assert client.post("/api/fpga/rain-predict", json={}).status_code == 503


def test_api_keeps_hardware_register_result(monkeypatch):
    class ConnectedBridge:
        def get_status(self):
            return {"connected": True, "version": "0x00010000"}

        def send_fusion(self, *_values):
            return {"fusion_score": 50, "stress_index": 20, "alert_level": 1}

    async def advisory(*_args, **_kwargs):
        return '{"adjusted_fusion_score":99,"assessment":"Inspect the field."}'

    monkeypatch.setattr(fpga_routes, "get_fpga_bridge", ConnectedBridge)
    monkeypatch.setattr(fpga_routes, "invoke_llm", advisory)
    app = FastAPI()
    app.include_router(fpga_routes.router)
    result = TestClient(app).post("/api/fpga/fusion", json={})
    assert result.status_code == 200
    assert result.json()["fpga_result"]["fusion_score"] == 50
    assert result.json()["ai_insights"] == "Inspect the field."


def test_canonical_api_uses_connected_registers(monkeypatch):
    from types import SimpleNamespace

    from skyview.agents import fpga_agent
    from skyview.api import v3_compat_routes, v3_routes
    from skyview.utils import config

    class ConnectedBridge:
        def get_status(self):
            return {"connected": True, "version": "0x00010000"}

        def send_fusion(self, *_values):
            return {"fusion_score": 50, "stress_index": 20, "alert_level": 1}

    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(ENABLE_FPGA=True))
    monkeypatch.setattr(fpga_agent, "get_fpga_bridge", ConnectedBridge)
    app = FastAPI()
    app.include_router(v3_routes.router)
    app.include_router(v3_compat_routes.router)
    app.dependency_overrides[v3_routes.identity] = lambda: "farmer-id"
    client = TestClient(app)
    status = client.get("/api/fpga/status")
    assert status.status_code == 200
    assert status.json()["physical_hardware_confirmed"] is True
    result = client.post("/api/fpga/fusion", json={})
    assert result.status_code == 200
    assert result.json()["fpga_result"]["fusion_score"] == 50
    assert client.post("/api/fpga/rain-predict", json={}).status_code == 503
