"""Adapts the campaign message into per-locale headline/subhead/CTA via a text LLM."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pipeline.models import BrandProfile, LocaleProfile, LocalizedCopy
from pipeline.providers.text_llm import TextLLMProvider

log = logging.getLogger(__name__)


_COPY_JSON_SCHEMA: dict = {
    "title": "localized_copy",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "headline": {"type": "string", "maxLength": 80},
        "subhead": {"type": "string", "maxLength": 160},
        "cta": {"type": "string", "maxLength": 40},
    },
    "required": ["headline", "subhead", "cta"],
}


_SOURCE_LANGUAGE = "English"


@dataclass(slots=True)
class CopyLocalizer:
    text_llm: TextLLMProvider | None = None

    async def localize(
        self,
        *,
        concept: str,
        brand: BrandProfile,
        locale_profile: LocaleProfile,
        force_llm: bool = False,
    ) -> LocalizedCopy:
        if self.text_llm is None or (
            not force_llm and locale_profile.language.lower().startswith("english")
        ):
            return LocalizedCopy(
                headline=concept.strip(),
                subhead="",
                cta="",
                language=locale_profile.locale,
                source="user",
            )

        system = (
            "You are a senior brand copywriter localizing a campaign for a specific market. "
            "You rewrite the source concept in-voice and in-language, never literal-translate. "
            "Output JSON with keys: headline (<=8 words), subhead (<=14 words), cta (<=4 words). "
            "Headline must be in the requested language and respect the brand voice. "
            "Never use any restricted phrases."
        )
        restricted_block = (
            ""
            if not brand.restricted_phrases
            else (
                "Restricted phrases (never include): "
                + ", ".join(brand.restricted_phrases)
                + ".\n"
            )
        )
        examples_block = (
            ""
            if not brand.tone_examples
            else "Tone examples (do not copy verbatim): " + " | ".join(brand.tone_examples) + ".\n"
        )
        cultural_block = (
            ""
            if not locale_profile.cultural_cues
            else "Cultural cues to honor: " + ", ".join(locale_profile.cultural_cues) + ".\n"
        )

        user = (
            f"Source concept (in {_SOURCE_LANGUAGE}): {concept.strip()}\n"
            f"Target language: {locale_profile.language} ({locale_profile.locale})\n"
            f"Brand: {brand.name}\n"
            f"Brand voice: {brand.voice}\n"
            f"{restricted_block}{examples_block}{cultural_block}"
            "Return JSON only."
        )

        try:
            payload = await self.text_llm.complete_json(
                system=system,
                user=user,
                schema=_COPY_JSON_SCHEMA,
                max_tokens=300,
                temperature=0.6,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("copy localizer LLM failed (%s); falling back to user concept", e)
            return LocalizedCopy(
                headline=concept.strip(),
                subhead="",
                cta="",
                language=locale_profile.locale,
                source="user",
            )

        headline = (payload.get("headline") or "").strip()
        subhead = (payload.get("subhead") or "").strip()
        cta = (payload.get("cta") or "").strip()

        if self._violates_restrictions(headline, subhead, cta, brand.restricted_phrases):
            log.warning(
                "copy localizer output contained restricted phrase; falling back to user concept",
            )
            return LocalizedCopy(
                headline=concept.strip(),
                subhead="",
                cta="",
                language=locale_profile.locale,
                source="user",
            )

        if not headline:
            headline = concept.strip()
        return LocalizedCopy(
            headline=headline[:120],
            subhead=subhead[:200],
            cta=cta[:60],
            language=locale_profile.locale,
            source="llm",
        )

    @staticmethod
    def _violates_restrictions(
        headline: str, subhead: str, cta: str, restricted: list[str],
    ) -> bool:
        if not restricted:
            return False
        haystack = f"{headline}\n{subhead}\n{cta}".lower()
        return any(phrase.lower() in haystack for phrase in restricted if phrase.strip())
