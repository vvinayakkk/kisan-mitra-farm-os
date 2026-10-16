"""Read-only local feature/download smoke with sanitized evidence, no credential output."""

import io
import json
import time
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
with httpx.Client(base_url="http://127.0.0.1:8001", timeout=15) as client:
    session = client.post("/api/assistant/sessions").json()
    headers = {
        "Authorization": "Bearer " + session["token"],
        "X-Assistant-Session": session["id"],
    }
    paths = [
        "/health",
        "/api/data/status",
        "/api/profile",
        "/api/sensors/latest/WS01",
        "/api/sensors/history/WS01",
        "/api/system-health",
        "/api/recent-alerts",
        "/api/trends/history",
        "/api/mandi/history?commodity=Rice&state=Andhra%20Pradesh&limit=3000",
        "/api/schemes",
        "/api/marketplace/directory",
        "/api/marketplace/pooling",
        "/api/weather/forecast?days=16",
        "/api/fpga/status",
        "/api/onboarding/options",
        "/api/farms",
        "/api/plots",
        "/api/crop-cycles",
        "/admin/tables",
        "/admin/tables/tasks?page_size=10",
    ]
    checks = {}
    for path in paths:
        start = time.perf_counter()
        response = client.get(path, headers=headers)
        checks[path] = {
            "status": response.status_code,
            "ms": round((time.perf_counter() - start) * 1000, 2),
            "cache": response.headers.get("cache-control"),
        }
        assert response.status_code == 200, (path, response.status_code)
    assert (
        client.post(
            "/api/chat/overview", headers=headers, json={"page": "overview"}
        ).status_code
        == 200
    )
    state = client.get(
        "/api/assistant/sessions/" + session["id"], headers=headers
    ).json()
    files = state["artifacts"]
    downloaded = {}
    for fmt in ("docx", "pdf", "xlsx", "csv", "pptx"):
        artifact = next(
            (
                a
                for a in files
                if a["format"] == fmt and a["title"] != "Database contract"
            ),
            None,
        )
        if not artifact:
            continue
        response = client.get(
            "/api/assistant/sessions/"
            + session["id"]
            + "/files/"
            + artifact["file_id"],
            headers=headers,
        )
        assert response.status_code == 200
        if fmt in ("docx", "xlsx", "pptx"):
            assert zipfile.is_zipfile(io.BytesIO(response.content))
        if fmt == "pdf":
            assert response.content.startswith(b"%PDF")
        downloaded[fmt] = {"bytes": len(response.content), "valid": True}
    station = client.get("/api/sensors/latest/WS01", headers=headers).json()
    report = {
        "backend": "persistent PostgreSQL v3",
        "routes": checks,
        "downloads": downloaded,
        "station": {
            "available": station["available"],
            "origin": station["data_origin"],
            "observed_at": station["timestamp"],
        },
        "tables": client.get("/api/data/status").json()["tables"],
        "directory_profiles": len(
            client.get("/api/marketplace/directory", headers=headers).json()["farmers"]
        ),
        "forecast_days": len(
            client.get("/api/weather/forecast?days=16", headers=headers).json()["records"]
        ),
    }
    out = ROOT.parents[1] / "outputs/skyview-v3-integration"
    out.mkdir(parents=True, exist_ok=True)
    (out / "http-validation.json").write_text(json.dumps(report, indent=2))
    private = ROOT / ".v3-data/restart-check.json"
    private.write_text(
        json.dumps(
            {
                "session": session,
                "message_count": len(state["messages"]),
                "task_count": len(state["tasks"]),
                "files": len(files),
            }
        )
    )
    private.chmod(0o600)
    print(json.dumps(report, indent=2))
