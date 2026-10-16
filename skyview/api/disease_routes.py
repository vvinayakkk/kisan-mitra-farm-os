"""Crop photo screening endpoints; bounded uploads and honest provider errors."""

import asyncio
import base64
import binascii
import logging
from typing import Annotated

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from skyview.agents.disease_service import (
    ALLOWED_FORMATS,
    COMMON_DISEASES,
    INDIAN_CROPS,
    MAX_IMAGE_BYTES,
    analyze_crop_image,
    persist_crop_assessment,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Crop photo screening"])


class Base64ImagePayload(BaseModel):
    image_base64: str = Field(
        min_length=1, max_length=((MAX_IMAGE_BYTES + 2) // 3) * 4 + 128
    )
    crop_hint: str | None = Field(default=None, max_length=100)
    crop_cycle_id: str | None = Field(default=None, max_length=36)


def _owner(authorization: str | None, sid: str | None):
    from skyview.data.v3.db import enabled

    if not enabled():
        return None
    from skyview.api.assistant_routes import authorize
    from skyview.assistant.store import farmer_id

    if not sid:
        raise HTTPException(401, "This crop check needs its workspace session.")
    authorize(sid, authorization)
    return farmer_id(sid)


async def _screen(content: bytes, crop_hint: str | None):
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Choose an image smaller than 5 MB.")
    try:
        return await analyze_crop_image(content, crop_hint=crop_hint)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            503, "Crop vision is unavailable. No diagnosis was made. Please retry."
        ) from exc
    except Exception as exc:
        logger.error("Crop screening failed (%s)", type(exc).__name__)
        raise HTTPException(
            503, "Crop screening is unavailable. No diagnosis was made."
        ) from exc


async def _persist(sid, content, result, filename, crop_cycle_id):
    try:
        return await asyncio.to_thread(
            persist_crop_assessment,
            sid,
            content,
            result,
            filename=filename,
            crop_cycle_id=crop_cycle_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except Exception as exc:
        logger.error("Crop assessment persistence failed (%s)", type(exc).__name__)
        raise HTTPException(
            503, "Your screening could not be saved. Please retry."
        ) from exc


@router.post("/disease/detect")
@router.post("/api/disease/detect")
async def detect_crop_disease(
    image: Annotated[UploadFile | None, File()] = None,
    crop_hint: str | None = Form(default=None, max_length=100),
    crop_cycle_id: str | None = Form(default=None, max_length=36),
    authorization: str | None = Header(default=None),
    x_assistant_session: str | None = Header(default=None),
):
    owner = _owner(authorization, x_assistant_session)
    if not image:
        raise HTTPException(400, "A crop photo is required.")
    if image.content_type and image.content_type not in {
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/octet-stream",
    }:
        raise HTTPException(400, "Use a JPEG, PNG or WebP crop photo.")
    content = await image.read(MAX_IMAGE_BYTES + 1)
    result = await _screen(content, crop_hint)
    case = (
        await _persist(
            x_assistant_session,
            content,
            result,
            image.filename or "crop-photo",
            crop_cycle_id,
        )
        if owner
        else {"saved": False}
    )
    return {
        "success": True,
        "filename": (image.filename or "crop-photo")[:120],
        "diagnostic": result,
        "case": case,
    }


@router.post("/disease/detect-base64")
@router.post("/api/disease/detect-base64")
async def detect_crop_disease_base64(
    payload: Base64ImagePayload,
    authorization: str | None = Header(default=None),
    x_assistant_session: str | None = Header(default=None),
):
    owner = _owner(authorization, x_assistant_session)
    raw = payload.image_base64
    if raw.startswith("data:"):
        prefix, separator, raw = raw.partition(",")
        if not separator or prefix not in {
            "data:image/jpeg;base64",
            "data:image/png;base64",
            "data:image/webp;base64",
        }:
            raise HTTPException(400, "Use a JPEG, PNG or WebP image data URL.")
    try:
        content = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(400, "This image is not valid base64.") from exc
    result = await _screen(content, payload.crop_hint)
    case = (
        await _persist(
            x_assistant_session, content, result, "crop-photo", payload.crop_cycle_id
        )
        if owner
        else {"saved": False}
    )
    return {"success": True, "diagnostic": result, "case": case}


@router.get("/disease/info")
@router.get("/api/disease/info")
async def get_pathology_catalog():
    return {
        "engine": "SkyView crop photo screening",
        "vision_models": ["qwen/qwen3.8-27b", "gemini-2.5-flash", "gemini-2.0-flash"],
        "recognized_crops": INDIAN_CROPS,
        "primary_pathologies": COMMON_DISEASES,
        "segmentation_output": "Visual boxes in image percentages; not validated lesion segmentation",
        "requires_confirmation": True,
        "formats": sorted(ALLOWED_FORMATS),
        "max_bytes": MAX_IMAGE_BYTES,
    }
