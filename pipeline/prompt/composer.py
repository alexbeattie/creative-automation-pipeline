"""Builds deterministic PromptSkeletons from brief + brand + locale via Jinja templates."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import (
    BaseLoader,
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateNotFound,
    select_autoescape,
)

from pipeline.models import (
    BrandProfile,
    CampaignBrief,
    Channel,
    LocaleProfile,
    Product,
    PromptConfig,
    PromptSkeleton,
)
from pipeline.prompt.config import default_prompt_config

log = logging.getLogger(__name__)

BUNDLED_TEMPLATE_DIR = Path(__file__).parent / "templates"


@dataclass(slots=True)
class PromptComposer:
    config: PromptConfig = field(default_factory=default_prompt_config)
    template_dir: Path | None = None

    _env: Environment = field(init=False)

    def __post_init__(self) -> None:
        loaders: list[BaseLoader] = []
        if self.template_dir is not None and Path(self.template_dir).exists():
            loaders.append(FileSystemLoader(str(self.template_dir)))
        loaders.append(FileSystemLoader(str(BUNDLED_TEMPLATE_DIR)))

        self._env = Environment(
            loader=ChoiceLoader(loaders),
            autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def build_skeleton(
        self,
        *,
        brief: CampaignBrief,
        product: Product,
        channel: Channel,
        brand: BrandProfile,
        locale_profile: LocaleProfile,
    ) -> PromptSkeleton:
        template_version = self._resolve_template_version(brand=brand, channel=channel)
        composition = self._composition_for(channel)
        avoid_list = list(dict.fromkeys(
            list(brand.must_avoid)
            + list(locale_profile.forbidden_imagery)
            + list(self.config.safety_directives)
        ))

        context = {
            "product_name": product.name,
            "product_description": product.description,
            "audience": brief.target_audience,
            "region": brief.target_region,
            "locale": brief.locale,
            "composition_directive": composition,
            "brand_name": brand.name,
            "brand_voice": brand.voice,
            "brand_palette": brand.palette,
            "brand_must_include": brand.must_include,
            "locale_language": locale_profile.language,
            "locale_aesthetic_keywords": locale_profile.aesthetic_keywords,
            "locale_cultural_cues": locale_profile.cultural_cues,
            "locale_seasonal_context": locale_profile.seasonal_context,
            "avoid_list": avoid_list,
        }

        try:
            template = self._env.get_template(f"{template_version}.j2")
        except TemplateNotFound:
            log.warning(
                "template %r not found (brand=%r channel=%s); falling back to %r",
                template_version, brand.id, channel.value,
                self.config.default_template_version,
            )
            template_version = self.config.default_template_version
            template = self._env.get_template(f"{template_version}.j2")

        rendered = template.render(**context).strip()

        trace = {
            "template_version": template_version,
            "channel": channel.value,
            "aspect_ratio": channel.native_ratio.value,
            "brand_id": brand.id,
            "brand_version": brand.version,
            "locale": locale_profile.locale,
            "product_id": product.id,
            "audience": brief.target_audience,
            "region": brief.target_region,
            "composition_directive": composition,
            "brand_palette": brand.palette,
            "brand_must_include": brand.must_include,
            "brand_must_avoid": brand.must_avoid,
            "locale_aesthetic_keywords": locale_profile.aesthetic_keywords,
            "locale_cultural_cues": locale_profile.cultural_cues,
            "locale_forbidden_imagery": locale_profile.forbidden_imagery,
        }

        return PromptSkeleton(
            template_version=template_version,
            deterministic_prompt=rendered,
            trace=trace,
        )

    def _resolve_template_version(self, *, brand: BrandProfile, channel: Channel) -> str:
        if brand.template_version:
            return brand.template_version
        if channel in self.config.templates_by_channel:
            return self.config.templates_by_channel[channel]
        return self.config.default_template_version

    def _composition_for(self, channel: Channel) -> str:
        try:
            return self.config.composition_by_channel[channel]
        except KeyError:
            log.warning("no composition_directive for channel %s; using empty", channel.value)
            return ""
