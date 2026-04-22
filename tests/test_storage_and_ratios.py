"""Tests for the filesystem storage layer and ratio lookups."""

from __future__ import annotations

import pytest

from pipeline.models import AspectRatio
from pipeline.processing.ratios import (
    NATIVE_SIZES,
    PLATFORM_TARGETS,
    Size,
    closest_native,
    native_size,
)
from pipeline.storage.filesystem import FilesystemStorage


class TestRatios:
    def test_native_sizes_match_gpt_image_1(self):
        assert NATIVE_SIZES[AspectRatio.SQUARE] == Size(1024, 1024)
        assert NATIVE_SIZES[AspectRatio.PORTRAIT] == Size(1024, 1536)
        assert NATIVE_SIZES[AspectRatio.LANDSCAPE] == Size(1536, 1024)

    def test_native_size_helper(self):
        assert native_size(AspectRatio.SQUARE) == Size(1024, 1024)

    @pytest.mark.parametrize("target,expected", [
        (Size(1080, 1080), AspectRatio.SQUARE),     # IG feed
        (Size(1080, 1920), AspectRatio.PORTRAIT),   # TikTok / Stories
        (Size(1080, 1350), AspectRatio.PORTRAIT),   # IG portrait
        (Size(1920, 1080), AspectRatio.LANDSCAPE),  # YouTube
        (Size(2000, 800),  AspectRatio.LANDSCAPE),  # extreme wide -> nearest landscape
    ])
    def test_closest_native(self, target, expected):
        assert closest_native(target) == expected

    def test_platform_targets_resolve_to_known_natives(self):
        for label, (size, ratio) in PLATFORM_TARGETS.items():
            assert ratio in NATIVE_SIZES, f"{label} maps to unknown ratio"
            assert size.width > 0 and size.height > 0


class TestFilesystemStorage:
    def test_relative_path_format(self, storage):
        rel = storage.relative_path_for(
            campaign_id="c123", product_id="serum", aspect_ratio=AspectRatio.PORTRAIT,
        )
        assert rel == "c123/serum/2-3.png"

    async def test_write_then_read_round_trip(self, storage):
        rel = await storage.write_asset(
            campaign_id="abc", product_id="prod",
            aspect_ratio=AspectRatio.SQUARE, png_bytes=b"\x89PNG\r\nDATA",
        )
        assert rel == "abc/prod/1-1.png"
        assert await storage.read_asset(rel) == b"\x89PNG\r\nDATA"

    async def test_write_creates_nested_directories(self, storage, tmp_path):
        await storage.write_asset(
            campaign_id="x", product_id="y",
            aspect_ratio=AspectRatio.LANDSCAPE, png_bytes=b"data",
        )
        assert (tmp_path / "output" / "x" / "y" / "3-2.png").exists()

    @pytest.mark.parametrize("evil", [
        "../../../etc/passwd",
        "../leaked.png",
        "x/../../../escape.png",
    ])
    def test_path_traversal_blocked(self, storage, evil):
        with pytest.raises(ValueError, match="escapes base_dir"):
            storage._resolve_safe(evil)

    def test_absolute_path_resolves_under_base_dir(self, storage, tmp_path):
        abs_path = storage.absolute_path("camp/prod/1-1.png")
        assert str(abs_path).startswith(str((tmp_path / "output").resolve()))
