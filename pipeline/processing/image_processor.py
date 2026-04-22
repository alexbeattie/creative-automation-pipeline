"""Pillow operations: overlay rendering and ratio conversion. Sync; wrap in to_thread."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pipeline.processing.ratios import Size


_FONT_FALLBACKS: tuple[str, ...] = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial.ttf",
)


@dataclass(slots=True, frozen=True)
class OverlaySpec:
    message: str
    font_path: str | None = None
    max_font_pt: int = 96
    margin_pct: float = 0.06
    stroke_pct: float = 0.04


class ImageProcessor:
    def apply_overlay(self, image_bytes: bytes, spec: OverlaySpec) -> bytes:
        """Render the campaign message over the image and return new PNG bytes."""
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")
        if not spec.message.strip():
            raise ValueError("overlay message must not be empty")

        img = Image.open(BytesIO(image_bytes)).convert("RGBA")
        W, H = img.size
        max_text_width = int(W * (1 - 2 * spec.margin_pct))
        message = spec.message.strip()

        font = self._fit_font(spec, message, max_text_width, max_font_h=int(H * 0.18))

        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), message, font=font, stroke_width=1)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        x = (W - text_w) // 2 - bbox[0]
        y = int(H * 0.72) - bbox[1]
        stroke = max(2, int(font.size * spec.stroke_pct))

        draw.text(
            (x, y),
            message,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=stroke,
            stroke_fill=(0, 0, 0, 220),
        )

        out = BytesIO()
        img.convert("RGB").save(out, format="PNG", optimize=True)
        return out.getvalue()

    def crop_to_ratio(self, image_bytes: bytes, target: Size) -> bytes:
        """Center-crop to target ratio, then resize to exact pixels."""
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")
        if target.width <= 0 or target.height <= 0:
            raise ValueError(f"target size must be positive, got {target}")

        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        src_w, src_h = img.size
        target_ratio = target.width / target.height
        src_ratio = src_w / src_h

        if src_ratio > target_ratio:
            new_w = int(src_h * target_ratio)
            offset = (src_w - new_w) // 2
            box = (offset, 0, offset + new_w, src_h)
        else:
            new_h = int(src_w / target_ratio)
            offset = (src_h - new_h) // 2
            box = (0, offset, src_w, offset + new_h)

        cropped = img.crop(box).resize((target.width, target.height), Image.LANCZOS)
        out = BytesIO()
        cropped.save(out, format="PNG", optimize=True)
        return out.getvalue()

    @staticmethod
    def _fit_font(
        spec: OverlaySpec, text: str, max_width_px: int, max_font_h: int,
    ) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
        font_path = spec.font_path or _first_existing(_FONT_FALLBACKS)
        if font_path is None:
            return ImageFont.load_default()

        size = min(spec.max_font_pt, max_font_h)
        while size > 12:
            font = ImageFont.truetype(font_path, size=size)
            bbox = font.getbbox(text)
            if (bbox[2] - bbox[0]) <= max_width_px:
                return font
            size -= 4
        return ImageFont.truetype(font_path, size=12)


def _first_existing(paths: tuple[str, ...]) -> str | None:
    for p in paths:
        if Path(p).exists():
            return p
    return None
