"""Concrete GenAIProvider for OpenAI gpt-image-1."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

from pipeline.models import AspectRatio
from pipeline.processing.ratios import native_size

log = logging.getLogger(__name__)

_OPENAI_SIZE: dict[AspectRatio, str] = {
    AspectRatio.SQUARE: "1024x1024",
    AspectRatio.PORTRAIT: "1024x1536",
    AspectRatio.LANDSCAPE: "1536x1024",
}


@dataclass(slots=True)
class OpenAIImageProvider:
    api_key: str
    model: str = "gpt-image-1"
    name: str = "openai:gpt-image-1"
    timeout_seconds: float = 120.0
    max_retries: int = 3

    async def generate(
        self,
        *,
        prompt: str,
        aspect_ratio: AspectRatio,
        seed: int | None = None,
    ) -> bytes:
        if not prompt or not prompt.strip():
            raise ValueError("prompt must be non-empty")
        if aspect_ratio not in _OPENAI_SIZE:
            raise ValueError(f"non-native ratio not supported by gpt-image-1: {aspect_ratio}")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _ = native_size(aspect_ratio)
        _ = seed  # gpt-image-1 has no public seed parameter

        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.api_key,
            timeout=self.timeout_seconds,
            max_retries=self.max_retries,
        )
        log.info("openai.images.generate: model=%s size=%s", self.model, _OPENAI_SIZE[aspect_ratio])
        try:
            resp = await client.images.generate(
                model=self.model,
                prompt=prompt,
                size=_OPENAI_SIZE[aspect_ratio],
                n=1,
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI image generation failed: {e}") from e

        if not resp.data or not resp.data[0].b64_json:
            raise RuntimeError("OpenAI returned an empty image payload")
        return base64.b64decode(resp.data[0].b64_json)
