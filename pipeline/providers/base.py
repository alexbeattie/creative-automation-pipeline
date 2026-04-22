"""Structural Protocol for any image-generation backend."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pipeline.models import AspectRatio


@runtime_checkable
class GenAIProvider(Protocol):
    name: str

    async def generate(
        self,
        *,
        prompt: str,
        aspect_ratio: AspectRatio,
        seed: int | None = None,
    ) -> bytes:
        """Generate one image at the requested native aspect ratio. Returns raw PNG bytes.

        Raises ValueError for invalid prompt or non-native ratio,
        RuntimeError if the upstream call fails after retries.
        """
        ...
