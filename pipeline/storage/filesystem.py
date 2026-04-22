"""Async writer/reader for campaign assets under OUTPUT_DIR."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import aiofiles
import aiofiles.os

from pipeline.models import AspectRatio


_RATIO_LABEL: dict[AspectRatio, str] = {
    AspectRatio.SQUARE: "1-1",
    AspectRatio.PORTRAIT: "2-3",
    AspectRatio.LANDSCAPE: "3-2",
}


@dataclass(slots=True)
class FilesystemStorage:
    base_dir: Path

    def __post_init__(self) -> None:
        self.base_dir = Path(self.base_dir).resolve()

    def relative_path_for(
        self,
        *,
        campaign_id: str,
        product_id: str,
        aspect_ratio: AspectRatio,
    ) -> str:
        return f"{campaign_id}/{product_id}/{_RATIO_LABEL[aspect_ratio]}.png"

    async def write_asset(
        self,
        *,
        campaign_id: str,
        product_id: str,
        aspect_ratio: AspectRatio,
        png_bytes: bytes,
    ) -> str:
        rel = self.relative_path_for(
            campaign_id=campaign_id,
            product_id=product_id,
            aspect_ratio=aspect_ratio,
        )
        abs_path = self._resolve_safe(rel)
        await aiofiles.os.makedirs(abs_path.parent, exist_ok=True)
        async with aiofiles.open(abs_path, "wb") as f:
            await f.write(png_bytes)
        return rel

    async def read_asset(self, relative_path: str) -> bytes:
        abs_path = self._resolve_safe(relative_path)
        async with aiofiles.open(abs_path, "rb") as f:
            return await f.read()

    def absolute_path(self, relative_path: str) -> Path:
        return self._resolve_safe(relative_path)

    def _resolve_safe(self, relative_path: str) -> Path:
        candidate = (self.base_dir / relative_path).resolve()
        if self.base_dir not in candidate.parents and candidate != self.base_dir:
            raise ValueError(f"path escapes base_dir: {relative_path}")
        return candidate
