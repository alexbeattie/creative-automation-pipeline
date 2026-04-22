"""Plans assets from a brief. No I/O, no async."""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.brand.registry import BrandRegistry, default_brand_profile
from pipeline.locale.registry import LocaleRegistry, default_locale_profile
from pipeline.models import (
    AspectRatio,
    AssetStrategy,
    BrandProfile,
    CampaignBrief,
    Channel,
    LocaleProfile,
    Product,
    PromptSkeleton,
    default_channel_for,
)
from pipeline.prompt.composer import PromptComposer


@dataclass(slots=True, frozen=True)
class AssetPlan:
    """One unit of work for the runner: what to make and how."""

    product: Product
    aspect_ratio: AspectRatio
    channel: Channel
    strategy: AssetStrategy
    brand: BrandProfile
    locale_profile: LocaleProfile
    skeleton: PromptSkeleton | None  # populated iff strategy == "generated"


@dataclass(slots=True)
class AssetOrchestrator:
    """Brain: turns a CampaignBrief into a flat list of AssetPlans."""

    brand_registry: BrandRegistry | None = None
    locale_registry: LocaleRegistry | None = None
    composer: PromptComposer = field(default_factory=PromptComposer)

    def plan(self, brief: CampaignBrief) -> list[AssetPlan]:
        """Cartesian product of products x (channels|aspect_ratios)."""
        brand = self._resolve_brand(brief.brand_profile_id)
        locale_profile = self._resolve_locale(brief.locale)

        if brief.channels:
            ratio_channel_pairs: list[tuple[AspectRatio, Channel]] = [
                (c.native_ratio, c) for c in brief.channels
            ]
        else:
            ratio_channel_pairs = [
                (r, default_channel_for(r)) for r in brief.aspect_ratios
            ]

        plans: list[AssetPlan] = []
        for product in brief.products:
            for ratio, channel in ratio_channel_pairs:
                strategy = self.determine_strategy(product, ratio)
                skeleton = (
                    self.composer.build_skeleton(
                        brief=brief,
                        product=product,
                        channel=channel,
                        brand=brand,
                        locale_profile=locale_profile,
                    )
                    if strategy == "generated"
                    else None
                )
                plans.append(
                    AssetPlan(
                        product=product,
                        aspect_ratio=ratio,
                        channel=channel,
                        strategy=strategy,
                        brand=brand,
                        locale_profile=locale_profile,
                        skeleton=skeleton,
                    ),
                )
        return plans

    def determine_strategy(
        self,
        product: Product,
        aspect_ratio: AspectRatio,
    ) -> AssetStrategy:
        """Crop when a source image is provided, otherwise generate."""
        _ = aspect_ratio
        if product.source_image_path:
            return "cropped"
        return "generated"

    def _resolve_brand(self, brand_id: str) -> BrandProfile:
        if self.brand_registry is None:
            return default_brand_profile()
        return self.brand_registry.get(brand_id)

    def _resolve_locale(self, locale: str) -> LocaleProfile:
        if self.locale_registry is None:
            return default_locale_profile(locale)
        return self.locale_registry.get(locale)
