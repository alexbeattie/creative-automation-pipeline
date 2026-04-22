"""Concrete TextLLMProvider for OpenAI chat completions (json_schema mode)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenAITextLLMProvider:
    api_key: str
    model: str = "gpt-4o-mini"
    name: str = "openai:gpt-4o-mini"

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = 600,
        temperature: float = 0.4,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.get("title", "result"),
                "schema": schema,
                "strict": True,
            },
        }
        try:
            resp = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=response_format,
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI JSON completion failed: {e}") from e

        if not resp.choices or not resp.choices[0].message.content:
            raise RuntimeError("OpenAI JSON completion returned empty content")
        try:
            return json.loads(resp.choices[0].message.content)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"OpenAI returned non-JSON despite json_schema: {e}") from e
