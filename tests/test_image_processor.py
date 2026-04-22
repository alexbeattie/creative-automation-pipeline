"""Pillow round-trip tests against the real ImageProcessor."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from pipeline.processing.image_processor import ImageProcessor, OverlaySpec
from pipeline.processing.ratios import Size


def _make_png(width: int, height: int, color=(120, 90, 200)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


class TestCrop:
    def test_crop_to_square_resizes_to_exact_dimensions(self):
        src = _make_png(2000, 1200)
        out = ImageProcessor().crop_to_ratio(src, Size(1024, 1024))
        img = Image.open(BytesIO(out))
        assert img.size == (1024, 1024)
        assert img.format == "PNG"

    def test_crop_to_landscape(self):
        src = _make_png(1000, 1000)
        out = ImageProcessor().crop_to_ratio(src, Size(1536, 1024))
        assert Image.open(BytesIO(out)).size == (1536, 1024)

    def test_crop_to_portrait(self):
        src = _make_png(1500, 1000)
        out = ImageProcessor().crop_to_ratio(src, Size(1024, 1536))
        assert Image.open(BytesIO(out)).size == (1024, 1536)


class TestOverlay:
    def test_overlay_returns_same_dimensions(self):
        src = _make_png(1024, 1024)
        out = ImageProcessor().apply_overlay(src, OverlaySpec(message="Glow Like Never Before"))
        img = Image.open(BytesIO(out))
        assert img.size == (1024, 1024)
        assert img.format == "PNG"

    def test_overlay_changes_pixels(self):
        src = _make_png(512, 512, color=(50, 50, 50))
        out = ImageProcessor().apply_overlay(src, OverlaySpec(message="Hello"))
        assert out != src
        assert len(out) > 100
