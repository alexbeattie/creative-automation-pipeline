"""POST /api/campaigns. Accepts multipart with the brief JSON and optional source images."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.deps import Settings, get_runner, get_settings
from pipeline.models import CampaignBrief, CampaignResult
from pipeline.runner import PipelineRunner

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignResult)
async def create_campaign(
    brief: str = Form(..., description="JSON-serialized CampaignBrief."),
    sources: list[UploadFile] = File(default=[], description="Optional source images, in product order."),
    runner: PipelineRunner = Depends(get_runner),
    settings: Settings = Depends(get_settings),
) -> CampaignResult:
    try:
        parsed = CampaignBrief.model_validate_json(brief)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors()) from e

    if sources:
        upload_root = settings.output_dir / "_uploads" / uuid4().hex[:12]
        upload_root.mkdir(parents=True, exist_ok=True)
        for i, upload in enumerate(sources):
            if i >= len(parsed.products):
                break
            if not upload or not upload.filename:
                continue
            dst = upload_root / f"{parsed.products[i].id}{Path(upload.filename).suffix or '.png'}"
            dst.write_bytes(await upload.read())
            parsed.products[i] = parsed.products[i].model_copy(
                update={"source_image_path": str(dst)},
            )

    log.info("running campaign: %s (%d products)", parsed.campaign_name, len(parsed.products))
    return await runner.run(parsed)
