"""Reusable async HTTP connection; stream public text and native tool calls only."""

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from itertools import count

import httpx

from skyview.utils.config import get_settings


logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class ProviderUnavailable(Exception):
    pass


def shared_quota_limit(response):
    """A provider organization limit cannot be bypassed with another API key."""
    if response.status_code == 413:
        return True
    if response.status_code != 429:
        return False
    try:
        message = response.json().get("error", {}).get("message", "").lower()
    except (ValueError, TypeError, AttributeError):
        return False
    return "organization" in message or "org-wide" in message


def inline_schema(schema):
    definitions = schema.get("$defs", {})

    def resolve(value):
        if isinstance(value, list):
            return [resolve(v) for v in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            return resolve(definitions[value["$ref"].split("/")[-1]])

        return {
            k: {name: resolve(field) for name, field in v.items()}
            if k == "properties"
            else resolve(v)
            for k, v in value.items()
            if k not in {"$defs", "title", "default"}
        }

    return resolve(schema)


def serving_schema(value):
    """Keep tool structure, defer costly decoding constraints to Pydantic.

    Gemini's required-call decoder rejects deeply nested bounded arrays (such
    as 500 spreadsheet rows). This affects inference only; executor validation
    still enforces every original size, numeric, format and ownership limit.
    """
    if isinstance(value, list):
        return [serving_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    constraints = {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minItems",
        "maxItems",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "multipleOf",
        "additionalProperties",
    }
    return {
        key: (
            {name: serving_schema(field) for name, field in item.items()}
            if key == "properties"
            else serving_schema(item)
        )
        for key, item in value.items()
        if key not in constraints
    }


def quota_delay(response):
    """Honor provider reset hints, including Google's daily quota RetryInfo."""
    try:
        header = float(response.headers.get("Retry-After", "0"))
    except ValueError:
        header = 0
    delay = max(15, header)
    try:
        body = response.json()
        body = body[0] if isinstance(body, list) and body else body
        for detail in body.get("error", {}).get("details", []):
            value = detail.get("retryDelay", "")
            if isinstance(value, str) and value.endswith("s"):
                delay = max(delay, float(value[:-1]))
    except (ValueError, TypeError, AttributeError):
        pass
    return min(delay, 86400)


_cooldowns: dict[str, float] = {}
_key_rotation = count()


async def _stream_attempt(
    client: httpx.AsyncClient, messages, tools, *, tool_choice="auto"
):
    settings = get_settings()
    keys = list(dict.fromkeys(settings.GROQ_API_KEYS))
    if keys:
        start = next(_key_rotation) % len(keys)
        keys = keys[start:] + keys[:start]
    candidates = [
        (
            "https://api.groq.com/openai/v1/chat/completions",
            key,
            os.getenv("ASSISTANT_MODEL", "openai/gpt-oss-120b"),
            True,
        )
        for key in keys
    ]
    if settings.GEMINI_API_KEY:
        candidates.append(
            (
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                settings.GEMINI_API_KEY,
                settings.GEMINI_MODEL,
                False,
            )
        )
    if not candidates:
        raise ProviderUnavailable("No AI provider is configured on the server.")
    groq_unavailable_for_request = False
    for url, key, model, groq in candidates:
        if groq and groq_unavailable_for_request:
            continue
        credential = hashlib.sha256((url + key + model).encode()).hexdigest()
        if _cooldowns.get(credential, 0) > time.monotonic():
            continue
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": 0.2,
            "max_tokens": 3000,
        }
        if tools:
            payload.update(
                {
                    "tools": tools
                    if groq
                    else [
                        {
                            **tool,
                            "function": {
                                **tool["function"],
                                "parameters": serving_schema(
                                    tool["function"]["parameters"]
                                ),
                            },
                        }
                        for tool in tools
                    ],
                    "tool_choice": tool_choice,
                }
            )
        if groq and model.startswith("openai/gpt-oss"):
            payload["reasoning_effort"] = os.getenv("ASSISTANT_REASONING_EFFORT", "low")
        started = False
        calls, content = {}, ""
        try:
            async with client.stream(
                "POST",
                url,
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
                timeout=httpx.Timeout(35, connect=5),
            ) as response:
                if response.status_code != 200:
                    logger.warning(
                        "Assistant provider rejected request: provider=%s model=%s status=%s",
                        "groq" if groq else "gemini",
                        model,
                        response.status_code,
                    )
                    await response.aread()
                    if response.status_code == 429:
                        _cooldowns[credential] = time.monotonic() + quota_delay(
                            response
                        )
                    if groq and shared_quota_limit(response):
                        groq_unavailable_for_request = True
                    if groq and response.status_code in (400, 404, 422):
                        groq_unavailable_for_request = True
                    continue
                yield {"type": "model", "model": model}
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    packet = json.loads(raw)
                    if packet.get("error"):
                        raise ProviderUnavailable(
                            "The AI provider interrupted this response."
                        )
                    for choice in packet.get("choices", []):
                        delta = choice.get("delta", {})
                        text = delta.get("content")

                        if text:
                            started = True
                            content += text
                            yield {"type": "delta", "text": text}
                        for position, part in enumerate(delta.get("tool_calls", [])):
                            call = calls.setdefault(
                                part.get("index", position),
                                {
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                },
                            )
                            if part.get("id"):
                                call["id"] = part["id"]
                            function = part.get("function", {})
                            call["function"]["name"] += function.get("name", "")
                            call["function"]["arguments"] += function.get(
                                "arguments", ""
                            )
                        if choice.get("finish_reason") == "length":
                            raise ProviderUnavailable(
                                "The response reached its length limit. Try a smaller task."
                            )
                if not content and not calls:
                    raise ProviderUnavailable(
                        "The AI provider returned an empty response."
                    )
                ordered = [calls[k] for k in sorted(calls)]
                for call in ordered:
                    call["id"] = call["id"] or uuid.uuid4().hex
                yield {
                    "type": "turn",
                    "message": {
                        "role": "assistant",
                        "content": content or None,
                        **({"tool_calls": ordered} if ordered else {}),
                    },
                }
                return
        except ProviderUnavailable:
            if started:
                raise
            continue
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            if started:
                raise ProviderUnavailable(
                    "The connection ended during the response. Please retry."
                ) from exc
    raise ProviderUnavailable(
        "The configured AI providers could not accept this request. Check credentials, quota and model availability."
    )


async def stream_turn(
    client: httpx.AsyncClient, messages, tools, *, tool_choice="auto", quota_wait=20
):
    """One bounded quota retry, before any content has been emitted.

    A running tool round is never replayed. Pending outputs survive a failed
    provider, and a cooldown produces explicit progress rather than a silent
    pause or hammering the exhausted key.
    """
    for attempt in range(2):
        emitted = False
        try:
            async for part in _stream_attempt(
                client, messages, tools, tool_choice=tool_choice
            ):
                emitted = True
                yield part
            return
        except ProviderUnavailable:
            waits = [
                deadline - time.monotonic()
                for deadline in _cooldowns.values()
                if deadline > time.monotonic()
            ]
            wait = min(waits) if waits else None
            if (
                emitted
                or attempt
                or not quota_wait
                or wait is None
                or wait > quota_wait
            ):
                raise
            yield {
                "type": "status",
                "label": "The AI service is busy; retrying shortly. Completed work is saved.",
            }
            await asyncio.sleep(wait + 0.05)
