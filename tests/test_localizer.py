"""Tests for the copy localizer (English fast path, restricted-phrase fallback)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pipeline.brand.registry import default_brand_profile
from pipeline.copy.localizer import CopyLocalizer
from pipeline.locale.registry import default_locale_profile
from pipeline.models import BrandProfile, LocaleProfile


@dataclass
class StubTextLLM:
    name: str = "stub:text"
    json_payload: dict[str, Any] = field(default_factory=dict)
    raises: bool = False
    json_calls: int = 0

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict,
        max_tokens: int = 600,
        temperature: float = 0.4,
    ) -> dict[str, Any]:
        self.json_calls += 1
        if self.raises:
            raise RuntimeError("boom")
        return self.json_payload


class TestEnglishFastPath:
    async def test_english_skips_llm(self):
        llm = StubTextLLM()
        localizer = CopyLocalizer(text_llm=llm)
        copy = await localizer.localize(
            concept="Glow Like Never Before",
            brand=default_brand_profile(),
            locale_profile=default_locale_profile("en-US"),
        )
        assert copy.headline == "Glow Like Never Before"
        assert copy.source == "user"
        assert llm.json_calls == 0

    async def test_no_llm_returns_user_verbatim(self):
        localizer = CopyLocalizer(text_llm=None)
        copy = await localizer.localize(
            concept="Hello",
            brand=default_brand_profile(),
            locale_profile=default_locale_profile("ja-JP"),
        )
        assert copy.source == "user"
        assert copy.headline == "Hello"


class TestLLMPath:
    async def test_llm_localized_copy_returned(self):
        llm = StubTextLLM(json_payload={
            "headline": "Strahlen wie nie zuvor",
            "subhead":  "Leichte Hydration für jeden Tag.",
            "cta":      "Jetzt entdecken",
        })
        localizer = CopyLocalizer(text_llm=llm)
        copy = await localizer.localize(
            concept="Glow Like Never Before",
            brand=default_brand_profile(),
            locale_profile=LocaleProfile(locale="de-DE", language="German"),
        )
        assert copy.source == "llm"
        assert copy.headline == "Strahlen wie nie zuvor"
        assert copy.cta == "Jetzt entdecken"

    async def test_restricted_phrase_falls_back(self):
        llm = StubTextLLM(json_payload={
            "headline": "A miracle for your skin",
            "subhead":  "",
            "cta":      "",
        })
        brand = BrandProfile(
            id="b", name="B", version="1", voice="v",
            restricted_phrases=["miracle"],
        )
        localizer = CopyLocalizer(text_llm=llm)
        copy = await localizer.localize(
            concept="Glow Like Never Before",
            brand=brand,
            locale_profile=LocaleProfile(locale="de-DE", language="German"),
        )
        assert copy.source == "user"
        assert copy.headline == "Glow Like Never Before"

    async def test_llm_failure_falls_back(self):
        llm = StubTextLLM(raises=True)
        localizer = CopyLocalizer(text_llm=llm)
        copy = await localizer.localize(
            concept="Glow Like Never Before",
            brand=default_brand_profile(),
            locale_profile=LocaleProfile(locale="de-DE", language="German"),
        )
        assert copy.source == "user"
