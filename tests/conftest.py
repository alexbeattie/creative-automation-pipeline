"""Shared test fixtures: fakes for provider/processor and a temp storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from pipeline.models import AspectRatio, CampaignBrief, Product
from pipeline.processing.image_processor import OverlaySpec
from pipeline.processing.ratios import Size
from pipeline.storage.filesystem import FilesystemStorage


@dataclass
class FakeProvider:
    name: str = "fake:test"
    calls: list[tuple[str, AspectRatio]] = field(default_factory=list)
    fail_on_prompt_substring: str | None = None

    async def generate(
        self,
        *,
        prompt: str,
        aspect_ratio: AspectRatio,
        seed: int | None = None,
    ) -> bytes:
        if self.fail_on_prompt_substring and self.fail_on_prompt_substring in prompt:
            raise RuntimeError(f"forced failure on prompt containing {self.fail_on_prompt_substring!r}")
        self.calls.append((prompt, aspect_ratio))
        return f"GEN[{aspect_ratio.value}]:{prompt}".encode()


class FakeProcessor:
    """Minimal ImageProcessor that just appends marker bytes (no Pillow needed)."""

    def apply_overlay(self, image_bytes: bytes, spec: OverlaySpec) -> bytes:
        return image_bytes + f"|overlay:{spec.message}".encode()

    def crop_to_ratio(self, image_bytes: bytes, target: Size) -> bytes:
        return image_bytes + f"|crop:{target.width}x{target.height}".encode()


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def fake_processor() -> FakeProcessor:
    return FakeProcessor()


@pytest.fixture
def storage(tmp_path: Path) -> FilesystemStorage:
    return FilesystemStorage(base_dir=tmp_path / "output")


@pytest.fixture
def source_image(tmp_path: Path) -> Path:
    """A pretend source PNG so the 'cropped' branch has bytes to read."""
    p = tmp_path / "hero.png"
    p.write_bytes(b"FAKE_SOURCE_IMAGE_BYTES")
    return p


@pytest.fixture
def brief_with_source(source_image: Path) -> CampaignBrief:
    return CampaignBrief(
        campaign_name="Spring Glow 2026",
        target_region="US",
        target_audience="Urban professionals 25-40",
        campaign_message="Glow Like Never Before",
        products=[
            Product(
                id="hydration-serum-50ml",
                name="Hydration Serum 50ml",
                description="Lightweight hyaluronic-acid serum.",
                source_image_path=str(source_image),
            ),
        ],
        aspect_ratios=[AspectRatio.SQUARE, AspectRatio.PORTRAIT, AspectRatio.LANDSCAPE],
    )
