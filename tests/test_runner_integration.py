"""Integration test: runner + composer + localizer + trace writer."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from pipeline.analytics.trace import FilesystemTraceWriter
from pipeline.brand.registry import BrandRegistry
from pipeline.copy.localizer import CopyLocalizer
from pipeline.locale.registry import LocaleRegistry
from pipeline.models import AspectRatio, CampaignBrief, Product
from pipeline.orchestrator import AssetOrchestrator
from pipeline.prompt.composer import PromptComposer
from pipeline.runner import PipelineRunner



@dataclass
class StubTextLLM:
    name: str = "stub:text"
    copy_payload: dict[str, Any] = field(default_factory=lambda: {
        "headline": "Strahlen wie nie zuvor",
        "subhead":  "Leichte Hydration für jeden Tag.",
        "cta":      "Jetzt entdecken",
    })
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
        return self.copy_payload


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def brand_dir(tmp_path):
    d = tmp_path / "brands"
    d.mkdir()
    (d / "spring_glow.yaml").write_text("""
id: spring_glow
name: Spring Glow
version: 2026.04.01
voice: Warm and confident.
palette: ["#F4C7C3"]
must_include: ["natural daylight"]
must_avoid: ["medical claims"]
restricted_phrases: ["miracle"]
tone_examples: ["Less effort. More glow."]
""".strip(), encoding="utf-8")
    return d


@pytest.fixture
def locale_dir(tmp_path):
    d = tmp_path / "locales"
    d.mkdir()
    (d / "de-DE.yaml").write_text("""
locale: de-DE
language: German
cultural_cues: ["understated Berlin sensibility"]
seasonal_context: "Late spring."
aesthetic_keywords: ["matte finishes"]
forbidden_imagery: ["religious symbols"]
currency: EUR
units: metric
""".strip(), encoding="utf-8")
    return d


@pytest.fixture
def integration_runner(fake_provider, fake_processor, storage, brand_dir, locale_dir, tmp_path):
    text_llm = StubTextLLM()
    composer = PromptComposer()
    localizer = CopyLocalizer(text_llm=text_llm)
    orchestrator = AssetOrchestrator(
        brand_registry=BrandRegistry(profiles_dir=brand_dir),
        locale_registry=LocaleRegistry(profiles_dir=locale_dir),
        composer=composer,
    )
    runner = PipelineRunner(
        provider=fake_provider,
        processor=fake_processor,
        storage=storage,
        orchestrator=orchestrator,
        localizer=localizer,
        trace_writer=FilesystemTraceWriter(base_dir=tmp_path / "output"),
    )
    return runner, text_llm


class TestIntegration:
    async def test_full_loop_produces_enriched_assets(self, integration_runner):
        runner, text_llm = integration_runner
        brief = CampaignBrief(
            campaign_name="Spring Glow 2026",
            target_region="EU-DE", locale="de-DE",
            brand_profile_id="spring_glow",
            target_audience="Berlin commuters",
            campaign_message="Glow Like Never Before",
            products=[Product(id="serum", name="Serum 50ml", description="Light serum.")],
            aspect_ratios=[AspectRatio.SQUARE],
        )
        result = await runner.run(brief)

        assert len(result.assets) == 1
        asset = result.assets[0]

        # Brand pinned + reported
        assert result.brand_profile_id == "spring_glow"
        assert result.brand_profile_version == "2026.04.01"

        # Deterministic prompt still carries the important context.
        assert asset.prompt is not None
        assert asset.prompt_trace["brand_id"] == "spring_glow"
        assert asset.prompt_trace["locale"] == "de-DE"
        assert "Serum 50ml" in asset.prompt

        # Localizer ran (de-DE -> LLM path)
        assert asset.copy is not None
        assert asset.copy.source == "llm"
        assert asset.copy.headline == "Strahlen wie nie zuvor"
        assert text_llm.json_calls == 1

    async def test_trace_jsonl_is_written(self, integration_runner, tmp_path):
        runner, _ = integration_runner
        brief = CampaignBrief(
            campaign_name="Spring Glow 2026",
            target_region="EU-DE", locale="de-DE",
            brand_profile_id="spring_glow",
            target_audience="Berlin commuters",
            campaign_message="Glow Like Never Before",
            products=[Product(id="serum", name="Serum 50ml", description="Light serum.")],
            aspect_ratios=[AspectRatio.SQUARE],
        )
        result = await runner.run(brief)

        trace_path = tmp_path / "output" / result.campaign_id / "trace.jsonl"
        assert trace_path.exists()
        rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
        assert len(rows) == 1
        row = rows[0]
        assert row["brand_id"] == "spring_glow"
        assert row["brand_version"] == "2026.04.01"
        assert row["locale"] == "de-DE"
        assert row["copy_source"] == "llm"

    async def test_idempotency_key_includes_brand_and_locale(
        self, integration_runner,
    ):
        runner, _ = integration_runner
        brief = CampaignBrief(
            campaign_name="C", target_region="EU-DE", locale="de-DE",
            brand_profile_id="spring_glow",
            target_audience="A", campaign_message="M",
            products=[Product(id="p", name="P", description="D")],
            aspect_ratios=[AspectRatio.SQUARE],
            idempotency_key="abcd1234ef",
        )
        first = await runner.run(brief)
        second = await runner.run(brief)
        assert first.campaign_id == second.campaign_id

        # Different brand id with same key MUST get a fresh run
        brief2 = brief.model_copy(update={"brand_profile_id": "default"})
        third = await runner.run(brief2)
        assert third.campaign_id != first.campaign_id
