"""GET /api/assets/{relative_path:path}. Serves PNGs from OUTPUT_DIR."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.deps import get_runner
from pipeline.runner import PipelineRunner

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/{relative_path:path}")
async def get_asset(
    relative_path: str,
    runner: PipelineRunner = Depends(get_runner),
) -> FileResponse:
    try:
        abs_path = runner.storage.absolute_path(relative_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail=f"asset not found: {relative_path}")
    return FileResponse(abs_path, media_type="image/png")
