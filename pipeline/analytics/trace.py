"""Append-only JSONL trace, one file per campaign."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import aiofiles
import aiofiles.os

log = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class AssetTraceEvent:
    campaign_id: str
    campaign_name: str
    product_id: str
    aspect_ratio: str
    channel: str | None
    strategy: str
    brand_id: str
    brand_version: str
    locale: str
    template_version: str | None
    prompt_skeleton_hash: str | None
    final_prompt: str | None
    copy_source: str | None
    copy_headline: str | None
    latency_ms: int
    relative_path: str
    warnings: list[str]

    def to_jsonl_row(self) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "product_id": self.product_id,
            "aspect_ratio": self.aspect_ratio,
            "channel": self.channel,
            "strategy": self.strategy,
            "brand_id": self.brand_id,
            "brand_version": self.brand_version,
            "locale": self.locale,
            "template_version": self.template_version,
            "prompt_skeleton_hash": self.prompt_skeleton_hash,
            "final_prompt": self.final_prompt,
            "copy_source": self.copy_source,
            "copy_headline": self.copy_headline,
            "latency_ms": self.latency_ms,
            "relative_path": self.relative_path,
            "warnings": self.warnings,
        }
        return json.dumps(payload, ensure_ascii=False) + "\n"


@runtime_checkable
class TraceWriter(Protocol):
    async def write(self, event: AssetTraceEvent) -> None: ...


class NoopTraceWriter:
    async def write(self, event: AssetTraceEvent) -> None:
        _ = event


@dataclass(slots=True)
class FilesystemTraceWriter:
    base_dir: Path

    def __post_init__(self) -> None:
        self.base_dir = Path(self.base_dir).resolve()

    async def write(self, event: AssetTraceEvent) -> None:
        try:
            campaign_dir = self.base_dir / event.campaign_id
            await aiofiles.os.makedirs(campaign_dir, exist_ok=True)
            async with aiofiles.open(campaign_dir / "trace.jsonl", "a", encoding="utf-8") as f:
                await f.write(event.to_jsonl_row())
        except Exception:  # noqa: BLE001
            log.exception("trace write failed for campaign %s", event.campaign_id)
