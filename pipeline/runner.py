"""Async runner. Takes plans from the orchestrator and produces assets."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import assert_never

from pipeline.analytics.trace import AssetTraceEvent, NoopTraceWriter, TraceWriter
from pipeline.copy.localizer import CopyLocalizer
from pipeline.models import (
    Asset,
    AssetStrategy,
    CampaignBrief,
    CampaignResult,
    LocalizedCopy,
)
from pipeline.orchestrator import AssetOrchestrator, AssetPlan
from pipeline.processing.image_processor import ImageProcessor, OverlaySpec
from pipeline.processing.ratios import native_size
from pipeline.providers.base import GenAIProvider
from pipeline.storage.filesystem import FilesystemStorage

log = logging.getLogger(__name__)


@dataclass(slots=True)
class PipelineRunner:
    provider: GenAIProvider
    processor: ImageProcessor
    storage: FilesystemStorage
    orchestrator: AssetOrchestrator = field(default_factory=AssetOrchestrator)
    localizer: CopyLocalizer | None = None
    trace_writer: TraceWriter = field(default_factory=NoopTraceWriter)
    _cache: dict[str, CampaignResult] = field(default_factory=dict, init=False)

    async def run(self, brief: CampaignBrief) -> CampaignResult:
        plans = self.orchestrator.plan(brief)
        if not plans:
            return CampaignResult(campaign_name=brief.campaign_name, assets=[])
        brand = plans[0].brand
        locale_profile = plans[0].locale_profile
        cache_key = self._cache_key(
            brief,
            brand_id=brand.id,
            brand_version=brand.version,
            locale=locale_profile.locale,
        )
        if cache_key and cache_key in self._cache:
            log.info("idempotency hit: returning cached result for %s", cache_key)
            return self._cache[cache_key]

        result = CampaignResult(
            campaign_name=brief.campaign_name,
            brand_profile_id=brand.id,
            brand_profile_version=brand.version,
            assets=[],
        )

        copy = await self._localize_once(brief, plans)
        if copy is not None and copy.source == "llm" and not copy.headline:
            copy = LocalizedCopy(
                headline=brief.campaign_message,
                language=locale_profile.locale,
                source="user",
            )

        overlay_message = (copy.headline if copy is not None else brief.campaign_message)
        overlay = OverlaySpec(message=overlay_message)

        async def _safe(plan: AssetPlan) -> Asset | str:
            try:
                return await self._execute_plan(
                    campaign_id=result.campaign_id,
                    campaign_name=result.campaign_name,
                    plan=plan,
                    overlay=overlay,
                    copy=copy,
                )
            except Exception as e:  # noqa: BLE001
                log.exception(
                    "plan failed: product=%s ratio=%s",
                    plan.product.id, plan.aspect_ratio,
                )
                return f"product '{plan.product.id}' ratio {plan.aspect_ratio.value}: {e}"

        outcomes = await asyncio.gather(*(_safe(p) for p in plans))
        for outcome in outcomes:
            if isinstance(outcome, Asset):
                result.assets.append(outcome)
            else:
                result.warnings.append(outcome)

        if cache_key:
            self._cache[cache_key] = result
        return result

    async def _execute_plan(
        self,
        *,
        campaign_id: str,
        campaign_name: str,
        plan: AssetPlan,
        overlay: OverlaySpec,
        copy: LocalizedCopy | None,
    ) -> Asset:
        started_at = time.perf_counter()

        skeleton = plan.skeleton
        final_prompt = skeleton.deterministic_prompt if skeleton is not None else None

        raw_bytes = await self._produce_raw_bytes(plan, final_prompt)
        composited = await asyncio.to_thread(
            self.processor.apply_overlay, raw_bytes, overlay,
        )
        relative_path = await self.storage.write_asset(
            campaign_id=campaign_id,
            product_id=plan.product.id,
            aspect_ratio=plan.aspect_ratio,
            png_bytes=composited,
        )

        size = native_size(plan.aspect_ratio)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        prompt_trace = dict(skeleton.trace) if skeleton is not None else {}
        if skeleton is not None:
            prompt_trace["prompt_skeleton_hash"] = skeleton.stable_hash()

        asset = Asset(
            product_id=plan.product.id,
            aspect_ratio=plan.aspect_ratio,
            channel=plan.channel,
            width=size.width,
            height=size.height,
            strategy=plan.strategy,
            relative_path=relative_path,
            prompt=final_prompt,
            copy=copy,
            prompt_trace=prompt_trace,
        )

        await self.trace_writer.write(
            AssetTraceEvent(
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                product_id=plan.product.id,
                aspect_ratio=plan.aspect_ratio.value,
                channel=plan.channel.value,
                strategy=plan.strategy,
                brand_id=plan.brand.id,
                brand_version=plan.brand.version,
                locale=plan.locale_profile.locale,
                template_version=skeleton.template_version if skeleton else None,
                prompt_skeleton_hash=prompt_trace.get("prompt_skeleton_hash"),
                final_prompt=final_prompt,
                copy_source=copy.source if copy else None,
                copy_headline=copy.headline if copy else None,
                latency_ms=latency_ms,
                relative_path=relative_path,
                warnings=[],
            ),
        )

        return asset

    async def _produce_raw_bytes(
        self,
        plan: AssetPlan,
        final_prompt: str | None,
    ) -> bytes:
        strategy: AssetStrategy = plan.strategy
        if strategy == "generated":
            assert final_prompt is not None
            return await self.provider.generate(
                prompt=final_prompt,
                aspect_ratio=plan.aspect_ratio,
            )
        if strategy == "cropped":
            assert plan.product.source_image_path is not None
            source_bytes = await asyncio.to_thread(
                _read_file_bytes, plan.product.source_image_path,
            )
            target = native_size(plan.aspect_ratio)
            return await asyncio.to_thread(
                self.processor.crop_to_ratio, source_bytes, target,
            )
        assert_never(strategy)

    async def _localize_once(
        self,
        brief: CampaignBrief,
        plans: list[AssetPlan],
    ) -> LocalizedCopy | None:
        if not plans:
            return None
        if self.localizer is None:
            return LocalizedCopy(
                headline=brief.campaign_message,
                language=plans[0].locale_profile.locale,
                source="user",
            )
        try:
            return await self.localizer.localize(
                concept=brief.campaign_message,
                brand=plans[0].brand,
                locale_profile=plans[0].locale_profile,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("copy localizer raised (%s); using user-typed message", e)
            return LocalizedCopy(
                headline=brief.campaign_message,
                language=plans[0].locale_profile.locale,
                source="user",
            )

    @staticmethod
    def _cache_key(
        brief: CampaignBrief,
        *,
        brand_id: str,
        brand_version: str,
        locale: str,
    ) -> str | None:
        if not brief.idempotency_key:
            return None
        return f"{brief.idempotency_key}|{brand_id}|{brand_version}|{locale}"


def _read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()
