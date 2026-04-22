"""Structural Protocol for any text-LLM backend used for schema-shaped completions."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TextLLMProvider(Protocol):
    name: str

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = 600,
        temperature: float = 0.4,
    ) -> dict[str, Any]:
        """Returns parsed JSON conforming to `schema`."""
        ...
