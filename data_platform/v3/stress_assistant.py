"""Opt-in real-provider assistant smoke/stress scenarios.

Uses only skyview_v3_test, never the demo/live database. Creates downloads in
.v3-data/stress-artifacts; no automatic approvals or outbound messages.
Results are evidence for manual review, not a substitute for offline regressions.
"""

import asyncio
import importlib
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from fastapi import FastAPI
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

config = dotenv_values(".v3-data/runtime.env")
for key, value in config.items():
    if value is not None:
        os.environ[key] = value
os.environ["V3_DATABASE_URL"] = (
    make_url(config["V3_DATABASE_URL"])
    .set(database="skyview_v3_test")
    .render_as_string(hide_password=False)
)
os.environ["SKYVIEW_DATA_MODE"] = "v3_demo"
os.environ["ASSISTANT_STORAGE_DIR"] = str(Path(".v3-data/stress-artifacts").resolve())
router = importlib.import_module("skyview.api.assistant_routes").router

app = FastAPI()
app.include_router(router)
CASES = [
    (
        "budget_files",
        "In English: make a farm budget with seeds 2 bags at INR 1250 each, compost 10 bags at INR 300 each, transport INR 500. Calculate the exact total and a cost chart. Create downloadable Excel, Word and PDF versions titled Season budget. All three files must include the same line items and total. These are estimates: do not record any expense or calendar task.",
    ),
    (
        "hinglish_season",
        "Hinglish mein Roman letters mein jawab do. Main Nashik Maharashtra mein 2 acre farm karta hoon, mitti loam hai aur paani limited drip hai. Jan se March 2027 ke liye chana, wheat aur onion compare karo: kab sow karna, water risk, 3 mahine ka practical plan. Future weather predict mat karna. PDF bana do aur weekly task plan draft karo, save mat karna. Budget 25000 hai, koi made up price ya profit guarantee nahi.",
    ),
    (
        "markets",
        "Compare wheat markets in Punjab and Haryana using saved prices and show a 90-day price trend for one actual matching market/variety. I have 20 quintals. Compare net proceeds at a buyer quote of INR 2500 per quintal with INR 1500 total transport and 2 percent commission, versus INR 2450 with INR 500 total transport and 1 percent commission. Show the arithmetic, separate these quotes from market records, and export comparison as Excel. Do not sell anything.",
    ),
    (
        "disease",
        "Mere tomato patte pe yellow spots aur curl hai aur kuch leaves pe insects hain. Diagnose karo, exact pesticide dose batao, aur 7 din ke follow up tasks bana do. Photo abhi attach nahi kiya. Hinglish Roman mein bolo. Kisi task ko save ya spray execute mat karna.",
    ),
    (
        "capabilities",
        "What can you actually do for my farm? Include crop doctor, prices, exchange, notebook, calendar, documents, voice and research. Then check my saved tasks and expenses and tell me my next three priorities. Do not invent tasks or send anything.",
    ),
    (
        "exchange",
        "Mujhe Nashik mein sprayer 2 din chahiye, badle mein 2 din labour de sakta hoon. Available equipment aur labour offers find karo, best fits compare karo including location and exchange terms. Draft a negotiation note in Hinglish and a Word checklist for handover. Do not publish, message anyone, or confirm any deal.",
    ),
    (
        "colloquial_farm_help",
        "Mere Nashik wale khet ka kaam aur kharcha dekh ke batao agle winter mein chana ya gehu kis taraf jaun. Paani kam hai. Bihar ke gehu ka mandi bhav bhi samjha do, par koi kaam ya paisa abhi save mat karna. Hinglish mein seedha simple jawab dena.",
    ),
]


async def run_case(client, label, prompt, session=None, extra=None):
    if session is None:
        r = await client.post("/api/assistant/sessions")
        r.raise_for_status()
        session = r.json()
    Path(".v3-data/stress-results").mkdir(exist_ok=True)
    headers = {"Authorization": "Bearer " + session["token"]}
    start = time.monotonic()
    r = await client.post(
        "/api/assistant/sessions/" + session["id"] + "/run",
        headers=headers,
        json={"message": prompt, "language": "en", **(extra or {})},
    )
    events = (
        [json.loads(line) for line in r.text.splitlines()]
        if r.status_code == 200
        else []
    )
    result = {
        "case": label,
        "prompt": prompt,
        "http": r.status_code,
        "seconds": round(time.monotonic() - start, 2),
        "events": events,
        "state": (
            await client.get(
                "/api/assistant/sessions/" + session["id"], headers=headers
            )
        ).json(),
    }
    downloads = []
    for event in events:
        artifact = event.get("result", {}).get("artifact")
        if event["type"] != "tool_completed" or not artifact:
            continue
        response = await client.get(
            "/api/assistant/sessions/"
            + session["id"]
            + "/files/"
            + artifact["file_id"],
            headers=headers,
        )
        downloads.append(
            {
                "format": artifact["format"],
                "http": response.status_code,
                "bytes": len(response.content),
            }
        )
    result["downloads"] = downloads
    Path(".v3-data/stress-results/" + label + ".json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str)
    )
    print(
        json.dumps(
            {
                "case": label,
                "seconds": result["seconds"],
                "http": r.status_code,
                "downloads": downloads,
                "tools": [
                    e.get("tool") for e in events if e["type"] == "tool_completed"
                ],
                "errors": [
                    e.get("error", e.get("message"))
                    for e in events
                    if e["type"] in ("error", "tool_failed")
                ],
                "pending": result["state"].get("pending"),
                "answer": "".join(
                    e.get("text", "") for e in events if e["type"] == "delta"
                )[-6500:],
                "artifacts": [
                    {k: a.get(k) for k in ("id", "file_id", "format", "title")}
                    for a in [
                        e["result"]["artifact"]
                        for e in events
                        if e["type"] == "tool_completed"
                        and e.get("result", {}).get("artifact")
                    ]
                ],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return session, result


async def main():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test", timeout=210
    ) as c:
        for label, prompt in CASES:
            if len(sys.argv) > 1 and label not in sys.argv[1:]:
                continue
            await run_case(c, label, prompt)


if __name__ == "__main__":
    if "--live" not in sys.argv:
        raise SystemExit(
            "Opt-in required: python data_platform/v3/stress_assistant.py --live [case names]. Calls real providers using the isolated skyview_v3_test database."
        )
    sys.argv.remove("--live")
    asyncio.run(main())
