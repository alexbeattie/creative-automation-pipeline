"""Tests for the orchestrator (planning logic, no I/O)."""

from __future__ import annotations

import pytest

from pipeline.brand.registry import default_brand_profile
from pipeline.locale.registry import default_locale_profile
from pipeline.models import AspectRatio, CampaignBrief, Channel, Product
from pipeline.orchestrator import AssetOrchestrator
from pipeline.prompt.composer import PromptComposer


@pytest.fixture
def orch() -> AssetOrchestrator:
    return AssetOrchestrator(composer=PromptComposer())


class TestStrategy:
    def test_source_present_returns_cropped(self, orch):
        p = Product(id="p", name="P", description="D", source_image_path="./hero.png")
        assert orch.determine_strategy(p, AspectRatio.SQUARE) == "cropped"

    def test_no_source_returns_generated(self, orch):
        p = Product(id="p", name="P", description="D")
        assert orch.determine_strategy(p, AspectRatio.SQUARE) == "generated"

    def test_plan_mixes_strategies(self, orch):
        brief = CampaignBrief(
            campaign_name="C", target_region="US",
            target_audience="A", campaign_message="M",
            products=[
                Product(id="p1", name="P1", description="D",
                        source_image_path="./hero.png"),
                Product(id="p2", name="P2", description="D"),
            ],
            aspect_ratios=[AspectRatio.SQUARE],
        )
        plans = orch.plan(brief)
        by_id = {p.product.id: p for p in plans}
        assert by_id["p1"].strategy == "cropped"
        assert by_id["p1"].skeleton is None
        assert by_id["p2"].strategy == "generated"
        assert by_id["p2"].skeleton is not None
        assert "P2" in by_id["p2"].skeleton.deterministic_prompt


class TestPlan:
    def test_one_plan_per_product_per_ratio(self, orch):
        brief = CampaignBrief(
            campaign_name="C", target_region="US",
            target_audience="A", campaign_message="M",
            products=[
                Product(id="p1", name="P1", description="D", source_image_path="./a.png"),
                Product(id="p2", name="P2", description="D", source_image_path="./b.png"),
            ],
            aspect_ratios=[AspectRatio.SQUARE, AspectRatio.PORTRAIT],
        )
        plans = orch.plan(brief)
        assert len(plans) == 4  # 2 products x 2 ratios
        assert {(p.product.id, p.aspect_ratio) for p in plans} == {
            ("p1", AspectRatio.SQUARE),
            ("p1", AspectRatio.PORTRAIT),
            ("p2", AspectRatio.SQUARE),
            ("p2", AspectRatio.PORTRAIT),
        }

    def test_cropped_plans_have_no_skeleton(self, orch):
        brief = CampaignBrief(
            campaign_name="C", target_region="US",
            target_audience="A", campaign_message="M",
            products=[Product(id="p", name="P", description="D",
                              source_image_path="./hero.png")],
        )
        for plan in orch.plan(brief):
            assert plan.strategy == "cropped"
            assert plan.skeleton is None

    def test_brand_and_locale_are_pinned_to_each_plan(self, orch):
        brief = CampaignBrief(
            campaign_name="C", target_region="US", locale="de-DE",
            target_audience="A", campaign_message="M",
            products=[Product(id="p", name="P", description="D")],
            aspect_ratios=[AspectRatio.SQUARE],
        )
        plan = orch.plan(brief)[0]
        # default brand falls back to the built-in profile
        assert plan.brand.id == "default"
        assert plan.locale_profile.locale == "de-DE"

    def test_channels_field_overrides_aspect_ratios(self, orch):
        brief = CampaignBrief(
            campaign_name="C", target_region="US",
            target_audience="A", campaign_message="M",
            products=[Product(id="p", name="P", description="D")],
            channels=[Channel.STORY_VERTICAL, Channel.DISPLAY_BANNER],
        )
        plans = orch.plan(brief)
        assert {p.channel for p in plans} == {Channel.STORY_VERTICAL, Channel.DISPLAY_BANNER}
        assert {p.aspect_ratio for p in plans} == {AspectRatio.PORTRAIT, AspectRatio.LANDSCAPE}


class TestDeterministicPrompt:
    def test_prompt_includes_product_audience_locale_brand(self, orch):
        brief = CampaignBrief(
            campaign_name="C", target_region="EU-DE", locale="de-DE",
            target_audience="Berlin commuters",
            campaign_message="M",
            products=[Product(id="p", name="MyProduct", description="MyDesc")],
            aspect_ratios=[AspectRatio.SQUARE],
        )
        plan = orch.plan(brief)[0]
        prompt = plan.skeleton.deterministic_prompt
        assert "MyProduct" in prompt
        assert "MyDesc" in prompt
        assert "Berlin commuters" in prompt
        assert "EU-DE" in prompt
        assert "de-DE" in prompt
        # default brand voice gets injected
        assert "Default" in prompt or "Clean" in prompt
        # Locale-aware aesthetic comes from the (synthesized) default locale profile
        assert "modern" in prompt.lower()

    def test_prompt_changes_per_aspect_ratio(self, orch):
        brief = CampaignBrief(
            campaign_name="C", target_region="US",
            target_audience="A", campaign_message="M",
            products=[Product(id="p", name="P", description="D")],
        )
        plans = orch.plan(brief)
        prompts = {p.aspect_ratio: p.skeleton.deterministic_prompt for p in plans}
        # Each composition directive differs per default channel/ratio.
        assert len(set(prompts.values())) == 3

    def test_skeleton_trace_is_populated(self, orch):
        brief = CampaignBrief(
            campaign_name="C", target_region="US",
            target_audience="A", campaign_message="M",
            products=[Product(id="p", name="P", description="D")],
            aspect_ratios=[AspectRatio.SQUARE],
        )
        plan = orch.plan(brief)[0]
        trace = plan.skeleton.trace
        assert trace["template_version"] == "skeleton_v1"
        assert trace["channel"] == Channel.SOCIAL_FEED_SQUARE.value
        assert trace["brand_id"] == "default"
        assert trace["locale"] == "en-US"


class TestStableHash:
    def test_same_inputs_same_hash(self):
        composer = PromptComposer()
        brand = default_brand_profile()
        loc = default_locale_profile("en-US")
        product = Product(id="p", name="P", description="D")
        brief = CampaignBrief(
            campaign_name="C", target_region="US",
            target_audience="A", campaign_message="M",
            products=[product], aspect_ratios=[AspectRatio.SQUARE],
        )
        a = composer.build_skeleton(
            brief=brief, product=product, channel=Channel.SOCIAL_FEED_SQUARE,
            brand=brand, locale_profile=loc,
        )
        b = composer.build_skeleton(
            brief=brief, product=product, channel=Channel.SOCIAL_FEED_SQUARE,
            brand=brand, locale_profile=loc,
        )
        assert a.stable_hash() == b.stable_hash()

    def test_different_channel_different_hash(self):
        composer = PromptComposer()
        brand = default_brand_profile()
        loc = default_locale_profile("en-US")
        product = Product(id="p", name="P", description="D")
        brief = CampaignBrief(
            campaign_name="C", target_region="US",
            target_audience="A", campaign_message="M",
            products=[product], aspect_ratios=[AspectRatio.SQUARE],
        )
        a = composer.build_skeleton(
            brief=brief, product=product, channel=Channel.SOCIAL_FEED_SQUARE,
            brand=brand, locale_profile=loc,
        )
        b = composer.build_skeleton(
            brief=brief, product=product, channel=Channel.STORY_VERTICAL,
            brand=brand, locale_profile=loc,
        )
        assert a.stable_hash() != b.stable_hash()
