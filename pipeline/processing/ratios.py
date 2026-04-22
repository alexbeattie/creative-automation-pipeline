"""gpt-image-1 native output sizes and platform-target mappings."""

from __future__ import annotations

from typing import NamedTuple

from pipeline.models import AspectRatio


class Size(NamedTuple):
    width: int
    height: int

    @property
    def ratio(self) -> float:
        return self.width / self.height


NATIVE_SIZES: dict[AspectRatio, Size] = {
    AspectRatio.SQUARE: Size(1024, 1024),
    AspectRatio.PORTRAIT: Size(1024, 1536),
    AspectRatio.LANDSCAPE: Size(1536, 1024),
}


# Platform-standard ratios mapped to the nearest native size for center-cropping.
PLATFORM_TARGETS: dict[str, tuple[Size, AspectRatio]] = {
    "1:1": (Size(1080, 1080), AspectRatio.SQUARE),
    "9:16": (Size(1080, 1920), AspectRatio.PORTRAIT),
    "4:5": (Size(1080, 1350), AspectRatio.PORTRAIT),
    "16:9": (Size(1920, 1080), AspectRatio.LANDSCAPE),
    "3:2": (Size(1536, 1024), AspectRatio.LANDSCAPE),
    "2:3": (Size(1024, 1536), AspectRatio.PORTRAIT),
}


def native_size(ratio: AspectRatio) -> Size:
    return NATIVE_SIZES[ratio]


def closest_native(target: Size) -> AspectRatio:
    """Return the native AspectRatio closest to `target`. Ties break toward SQUARE."""
    target_r = target.ratio
    best: tuple[float, AspectRatio] = (float("inf"), AspectRatio.SQUARE)
    for ratio, size in NATIVE_SIZES.items():
        delta = abs(size.ratio - target_r)
        if delta < best[0]:
            best = (delta, ratio)
    return best[1]
