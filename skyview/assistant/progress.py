"""Public execution progress, never fabricated reasoning or simulated completion."""

import asyncio
import time


async def live_events(source, interval=2.5):
    pending = None
    label = "Preparing your request"
    stage_started = time.monotonic()
    try:
        while True:
            if pending is None:
                pending = asyncio.create_task(anext(source))
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield {
                    "type": "status",
                    "label": f"{label} · {int(time.monotonic() - stage_started)}s elapsed",
                    "phase": "waiting",
                }
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                return
            pending = None
            kind = event.get("type")
            if kind == "tool_started":
                label = event.get("label", "Running the requested action")
                arguments = event.get("arguments", {})
                detail = next(
                    (
                        str(arguments[key])[:70]
                        for key in ("title", "commodity", "city", "query", "skill")
                        if arguments.get(key)
                    ),
                    "",
                )
                if detail:
                    label += f" — {detail}"
                event = {**event, "label": label}
            elif kind == "tool_completed":
                label = "Preparing the response from the completed action"
            elif kind == "model":
                label = "Waiting for the assistant response"
            elif kind == "status":
                label = event.get("label", label)
            if kind != "delta":
                stage_started = time.monotonic()
            yield event
    finally:
        if pending is not None:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        await source.aclose()
