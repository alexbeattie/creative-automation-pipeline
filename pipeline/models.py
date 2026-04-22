"""Pydantic models. Single source of truth for data crossing the pipeline boundary."""

from __future__ import annotations

import hashlib
import json
import warnings
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

warnings.filterwarnings(
    "ignore",
    message='Field name "copy" in "Asset" shadows an attribute in parent "BaseModel"',
    category=UserWarning,
)


class AspectRatio(str, Enum):
    SQUARE = "1:1"
    PORTRAIT = "2:3"
    LANDSCAPE = "3:2"

    @property
    def pixels(self) -> tuple[int, int]:
        return _RATIO_PIXELS[self]


_RATIO_PIXELS: dict[AspectRatio, tuple[int, int]] = {
    AspectRatio.SQUARE: (1024, 1024),
    AspectRatio.PORTRAIT: (1024, 1536),
    AspectRatio.LANDSCAPE: (1536, 1024),
}


class Channel(str, Enum):
    SOCIAL_FEED_SQUARE = "social_feed_square"
    SOCIAL_FEED_PORTRAIT = "social_feed_portrait"
    STORY_VERTICAL = "story_vertical"
    DISPLAY_LANDSCAPE = "display_landscape"
    DISPLAY_BANNER = "display_banner"

    @property
    def native_ratio(self) -> AspectRatio:
        return _CHANNEL_TO_RATIO[self]


_CHANNEL_TO_RATIO: dict[Channel, AspectRatio] = {
    Channel.SOCIAL_FEED_SQUARE: AspectRatio.SQUARE,
    Channel.SOCIAL_FEED_PORTRAIT: AspectRatio.PORTRAIT,
    Channel.STORY_VERTICAL: AspectRatio.PORTRAIT,
    Channel.DISPLAY_LANDSCAPE: AspectRatio.LANDSCAPE,
    Channel.DISPLAY_BANNER: AspectRatio.LANDSCAPE,
}

_DEFAULT_CHANNEL_FOR_RATIO: dict[AspectRatio, Channel] = {
    AspectRatio.SQUARE: Channel.SOCIAL_FEED_SQUARE,
    AspectRatio.PORTRAIT: Channel.SOCIAL_FEED_PORTRAIT,
    AspectRatio.LANDSCAPE: Channel.DISPLAY_LANDSCAPE,
}


def default_channel_for(ratio: AspectRatio) -> Channel:
    return _DEFAULT_CHANNEL_FOR_RATIO[ratio]


class Product(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(
        description="Stable identifier for the product (slug or SKU). Used in output paths.",
        examples=["hydration-serum-50ml"],
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9\-_]*$",
    )
    name: str = Field(
        description="Human-readable product name shown to creatives.",
        examples=["Hydration Serum 50ml"],
        min_length=1,
        max_length=120,
    )
    description: str = Field(
        description="Short product description. Fed into the GenAI prompt for context.",
        examples=["A lightweight hyaluronic-acid serum for daily use."],
        min_length=1,
        max_length=500,
    )
    source_image_path: str | None = Field(
        default=None,
        description=(
            "Optional path to an existing hero image. If present, the orchestrator "
            "MAY crop/resize this asset instead of generating a new one. If absent, "
            "all aspect ratios are generated via the GenAI provider."
        ),
        examples=["./assets/hydration-serum-50ml.png"],
    )


class BrandProfile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(
        description="Stable brand identifier matching the YAML filename.",
        examples=["spring_glow"],
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9\-_]*$",
    )
    name: str = Field(
        description="Human-readable brand name.",
        examples=["Spring Glow"],
        min_length=1,
        max_length=120,
    )
    version: str = Field(
        description="Brand-guideline revision. Bump on every meaningful edit.",
        examples=["2026.04.01"],
        min_length=1,
        max_length=32,
    )
    voice: str = Field(
        description="One-line voice/tone descriptor injected into every prompt.",
        examples=["Warm, confident, never hyperbolic. Speaks like a knowledgeable friend."],
        min_length=1,
        max_length=400,
    )
    palette: list[str] = Field(
        default_factory=list,
        description="Brand color hex codes (with leading '#'). Used as visual cues.",
        examples=[["#F4C7C3", "#2E2E2E", "#FFFFFF"]],
    )
    must_include: list[str] = Field(
        default_factory=list,
        description="Visual cues every generated image should include.",
        examples=[["natural daylight", "minimalist staging"]],
    )
    must_avoid: list[str] = Field(
        default_factory=list,
        description="Banned visuals, claims, and competitor references.",
        examples=[["medical claims", "before/after collages", "competitor logos"]],
    )
    restricted_phrases: list[str] = Field(
        default_factory=list,
        description="Phrases that must never appear in localized copy (substring match).",
        examples=[["miracle", "cure", "100% guaranteed"]],
    )
    tone_examples: list[str] = Field(
        default_factory=list,
        description="Few-shot examples of on-brand copy. Helps the copy LLM.",
        examples=[["Skin that wakes up before you do.", "Less effort. More glow."]],
    )
    template_version: str | None = Field(
        default=None,
        description=(
            "Optional brand-specific Jinja template stem under prompt_templates/. "
            "Overrides per-channel and default templates."
        ),
        examples=["skeleton_spring_glow_v1"],
        max_length=120,
    )


class LocaleProfile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    locale: str = Field(
        description="BCP-47 locale tag matching the YAML filename.",
        examples=["en-US", "de-DE", "ja-JP"],
        min_length=2,
        max_length=16,
        pattern=r"^[a-zA-Z]{2,3}([-_][a-zA-Z0-9]{2,8})*$",
    )
    language: str = Field(
        description="Human-readable language used by the copy LLM.",
        examples=["English", "German", "Japanese"],
        min_length=1,
        max_length=64,
    )
    cultural_cues: list[str] = Field(
        default_factory=list,
        description="Short phrases describing local cultural context for visuals.",
        examples=[["urban East Coast aesthetic", "diverse cast", "casual professional dress"]],
    )
    seasonal_context: str = Field(
        default="",
        description="Current seasonal/temporal hint, refreshed by ops.",
        examples=["Late spring, longer daylight, pastel-leaning palettes."],
        max_length=400,
    )
    aesthetic_keywords: list[str] = Field(
        default_factory=list,
        description="Visual aesthetic descriptors locals respond to.",
        examples=[["soft golden hour", "shallow depth of field", "documentary realism"]],
    )
    forbidden_imagery: list[str] = Field(
        default_factory=list,
        description="Imagery considered offensive or off-brand for this market.",
        examples=[["alcohol", "explicit gestures", "religious symbols"]],
    )
    currency: str = Field(
        default="",
        description="ISO-4217 currency hint for copy/CTA generation.",
        examples=["USD", "EUR", "JPY"],
        max_length=8,
    )
    units: Literal["metric", "imperial", ""] = Field(
        default="",
        description="Unit system for any copy that mentions measurements.",
    )


class PromptConfig(BaseModel):
    """Externalized prompt configuration loaded from prompt_config.yaml."""

    model_config = ConfigDict(str_strip_whitespace=True)

    default_template_version: str = Field(
        default="skeleton_v1",
        description="Filename stem of the fallback Jinja template.",
        examples=["skeleton_v1"],
        min_length=1,
        max_length=120,
    )
    templates_by_channel: dict[Channel, str] = Field(
        default_factory=dict,
        description=(
            "Optional per-channel template overrides. Keys are Channel values; "
            "values are template_version stems. Empty dict = use default for all."
        ),
        examples=[{"story_vertical": "skeleton_story_v1"}],
    )
    composition_by_channel: dict[Channel, str] = Field(
        default_factory=dict,
        description=(
            "Per-channel composition directive injected into the prompt. Required: "
            "every Channel value must be present (the registry validates on load)."
        ),
    )
    safety_directives: list[str] = Field(
        default_factory=list,
        description=(
            "Always-on brand-hygiene rules merged into every asset's avoid_list, "
            "independent of brand or locale."
        ),
        examples=[["no text rendered into the image", "no real public figures"]],
    )


class CampaignBrief(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    campaign_name: str = Field(
        description="Marketing campaign name. Used for grouping and reporting.",
        examples=["Spring Glow 2026"],
        min_length=1,
        max_length=120,
    )
    target_region: str = Field(
        description="ISO-style market code or region label. Influences localization tone.",
        examples=["US", "EU-DE", "APAC-JP"],
        min_length=2,
        max_length=16,
    )
    locale: str = Field(
        default="en-US",
        description="BCP-47 locale tag. Drives copy translation and locale prompt modifiers.",
        examples=["en-US", "de-DE", "ja-JP"],
        min_length=2,
        max_length=16,
        pattern=r"^[a-zA-Z]{2,3}([-_][a-zA-Z0-9]{2,8})*$",
    )
    target_audience: str = Field(
        description="Short audience persona descriptor. Fed into the GenAI prompt.",
        examples=["Urban professionals, 25-40, skincare-conscious"],
        min_length=1,
        max_length=240,
    )
    campaign_message: str = Field(
        description="The headline/CTA text rendered as an overlay on every asset.",
        examples=["Glow Like Never Before"],
        min_length=1,
        max_length=120,
    )
    products: list[Product] = Field(
        description="One or more products to generate creatives for.",
        min_length=1,
        max_length=20,
    )
    aspect_ratios: list[AspectRatio] = Field(
        default_factory=lambda: list(AspectRatio),
        description="Aspect ratios to produce per product. Defaults to all three native sizes.",
        examples=[["1:1", "2:3", "3:2"]],
        min_length=1,
    )
    channels: list[Channel] | None = Field(
        default=None,
        description="Optional channel expansion. When set, replaces aspect_ratios as the axis.",
        examples=[["social_feed_square", "story_vertical"]],
    )
    brand_profile_id: str = Field(
        default="default",
        description="ID of the BrandProfile to apply (matches a YAML in brand_profiles/).",
        examples=["spring_glow"],
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9\-_]*$",
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Optional client key. Repeat submissions return the cached result.",
        examples=["c1f4a8e2-7d3b-4f1a-9c0e-2b8a6e4d1c3f"],
        min_length=8,
        max_length=128,
    )

    @field_validator("aspect_ratios")
    @classmethod
    def _dedupe_ratios(cls, v: list[AspectRatio]) -> list[AspectRatio]:
        seen: set[AspectRatio] = set()
        out: list[AspectRatio] = []
        for r in v:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return out

    @field_validator("channels")
    @classmethod
    def _dedupe_channels(cls, v: list[Channel] | None) -> list[Channel] | None:
        if v is None:
            return None
        seen: set[Channel] = set()
        out: list[Channel] = []
        for c in v:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out


class PromptSkeleton(BaseModel):
    """Structured, versioned input/output of the PromptComposer."""

    model_config = ConfigDict(str_strip_whitespace=False)

    template_version: str = Field(
        description="Version of the skeleton template. Bumped when prompt structure changes.",
        examples=["skeleton_v1"],
    )
    deterministic_prompt: str = Field(
        description="Brand-safe prompt usable without any further LLM expansion.",
    )
    trace: dict = Field(
        default_factory=dict,
        description="Structured record of every input that went into the prompt.",
    )

    def stable_hash(self) -> str:
        canonical = self.model_dump(mode="json", exclude={"trace"})
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


AssetStrategy = Literal["generated", "cropped"]


class LocalizedCopy(BaseModel):
    headline: str = Field(
        description="Primary on-image overlay. Keep under ~40 chars for legibility.",
        examples=["Glow Like Never Before"],
        min_length=1,
        max_length=120,
    )
    subhead: str = Field(
        default="",
        description="Optional supporting line. May be empty.",
        examples=["Lightweight hydration that lasts."],
        max_length=200,
    )
    cta: str = Field(
        default="",
        description="Optional call to action. May be empty.",
        examples=["Shop now"],
        max_length=60,
    )
    language: str = Field(
        description="BCP-47 locale of the rendered copy.",
        examples=["en-US", "de-DE", "ja-JP"],
    )
    source: Literal["user", "llm"] = Field(
        description="Provenance: 'user' = typed verbatim, 'llm' = generated.",
    )


class Asset(BaseModel):
    # `copy` shadows BaseModel.copy (deprecated in Pydantic v2). Field name kept
    # to match the JSON contract the UI consumes. The shadow warning is filtered above.
    product_id: str = Field(
        description="Echo of the source Product.id this asset belongs to.",
        examples=["hydration-serum-50ml"],
    )
    aspect_ratio: AspectRatio = Field(
        description="Native aspect ratio of this asset.",
        examples=["1:1"],
    )
    channel: Channel | None = Field(
        default=None,
        description="Channel this asset was composed for. None for legacy/ratio-only briefs.",
        examples=["social_feed_square"],
    )
    width: int = Field(description="Final pixel width.", examples=[1024])
    height: int = Field(description="Final pixel height.", examples=[1024])
    strategy: AssetStrategy = Field(
        description="'generated' = GenAI call; 'cropped' = derived from source_image_path.",
        examples=["generated"],
    )
    relative_path: str = Field(
        description="Path relative to OUTPUT_DIR. Served by /api/assets.",
        examples=["spring-glow-2026/hydration-serum-50ml/1-1.png"],
    )
    prompt: str | None = Field(
        default=None,
        description="Final prompt sent to the provider, if strategy='generated'.",
        examples=["Editorial product shot of Hydration Serum 50ml ..."],
    )
    copy: LocalizedCopy | None = Field(
        default=None,
        description="Localized headline/subhead/CTA used for the overlay.",
    )
    prompt_trace: dict = Field(
        default_factory=dict,
        description="Structured record of inputs that produced the prompt.",
    )

    @field_validator("relative_path")
    @classmethod
    def _no_absolute_paths(cls, v: str) -> str:
        if Path(v).is_absolute() or v.startswith(".."):
            raise ValueError("relative_path must be relative and within OUTPUT_DIR")
        return v


class CampaignResult(BaseModel):
    campaign_id: str = Field(
        default_factory=lambda: uuid4().hex[:12],
        description="Server-assigned identifier. Doubles as the output directory name.",
        examples=["a1b2c3d4e5f6"],
    )
    campaign_name: str = Field(
        description="Echo of CampaignBrief.campaign_name.",
        examples=["Spring Glow 2026"],
    )
    brand_profile_id: str = Field(
        default="default",
        description="Echo of CampaignBrief.brand_profile_id for downstream attribution.",
    )
    brand_profile_version: str = Field(
        default="",
        description="Resolved BrandProfile.version at run time.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of pipeline completion.",
    )
    assets: list[Asset] = Field(
        description="All produced assets. Length = len(products) * len(aspect_ratios|channels).",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal issues surfaced to the operator. Empty on a clean run.",
        examples=[["product 'foo': source image too small for 3:2 crop, generated instead"]],
    )
