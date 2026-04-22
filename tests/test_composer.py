"""Tests for the prompt composer."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.brand.registry import default_brand_profile
from pipeline.locale.registry import default_locale_profile
from pipeline.models import (
    AspectRatio,
    BrandProfile,
    CampaignBrief,
    Channel,
    LocaleProfile,
    Product,
)
from pipeline.prompt.composer import PromptComposer
from pipeline.prompt.config import default_prompt_config


@pytest.fixture
def brief() -> CampaignBrief:
    return CampaignBrief(
        campaign_name="Spring Glow", target_region="US",
        target_audience="Urban professionals 25-40",
        campaign_message="Glow Like Never Before",
        products=[Product(id="serum", name="Serum 50ml", description="Lightweight serum.")],
        aspect_ratios=[AspectRatio.SQUARE],
    )


@pytest.fixture
def brand() -> BrandProfile:
    return default_brand_profile()


@pytest.fixture
def locale_profile() -> LocaleProfile:
    return default_locale_profile("en-US")


class TestPromptConfigDefaults:
    """The code-baked defaults should fully cover every Channel and have
    sensible safety directives. Production overrides via prompt_config.yaml."""

    def test_each_channel_has_a_composition_directive(self):
        cfg = default_prompt_config()
        for c in Channel:
            assert cfg.composition_by_channel[c]

    def test_default_safety_directives_present(self):
        cfg = default_prompt_config()
        assert any("text" in s.lower() for s in cfg.safety_directives)

    def test_default_template_version_is_set(self):
        cfg = default_prompt_config()
        assert cfg.default_template_version


class TestBuildSkeleton:
    def test_deterministic_prompt_contains_brand_and_locale(self, brief, brand, locale_profile):
        composer = PromptComposer()
        skel = composer.build_skeleton(
            brief=brief, product=brief.products[0], channel=Channel.SOCIAL_FEED_SQUARE,
            brand=brand, locale_profile=locale_profile,
        )
        p = skel.deterministic_prompt
        assert "Serum 50ml" in p
        assert "Lightweight serum" in p
        assert "Urban professionals 25-40" in p
        assert brand.name in p
        # default brand voice present
        assert any(word in p for word in brand.voice.split()[:3])
        # always-on safety directives end up in the avoid list
        assert "no text, captions, or watermarks rendered into the image" in p

    def test_avoid_list_merges_brand_locale_safety(self, brief):
        brand = BrandProfile(
            id="b", name="B", version="1",
            voice="v", must_avoid=["competitor logos"],
        )
        locale_profile = LocaleProfile(
            locale="xx-YY", language="X",
            forbidden_imagery=["religious symbols"],
        )
        composer = PromptComposer()
        skel = composer.build_skeleton(
            brief=brief, product=brief.products[0], channel=Channel.SOCIAL_FEED_SQUARE,
            brand=brand, locale_profile=locale_profile,
        )
        p = skel.deterministic_prompt
        assert "competitor logos" in p
        assert "religious symbols" in p

class TestTemplateResolution:
    """Brand override > channel override > config default."""

    def test_default_template_used_when_no_overrides(self, brief, brand, locale_profile):
        composer = PromptComposer()
        skel = composer.build_skeleton(
            brief=brief, product=brief.products[0], channel=Channel.SOCIAL_FEED_SQUARE,
            brand=brand, locale_profile=locale_profile,
        )
        assert skel.template_version == "skeleton_v1"
        assert skel.trace["template_version"] == "skeleton_v1"

    def test_channel_override_wins_over_default(self, brief, brand, locale_profile, tmp_path):
        # Need a real template file on disk for the override to render.
        templates = tmp_path / "tpl"
        templates.mkdir()
        (templates / "skeleton_alt.j2").write_text(
            "ALT TEMPLATE for {{ product_name }}\nAvoid: {{ avoid_list | join(', ') }}.",
        )
        cfg = default_prompt_config().model_copy(update={
            "templates_by_channel": {Channel.STORY_VERTICAL: "skeleton_alt"},
        })
        composer = PromptComposer(config=cfg, template_dir=templates)
        skel = composer.build_skeleton(
            brief=brief, product=brief.products[0], channel=Channel.STORY_VERTICAL,
            brand=brand, locale_profile=locale_profile,
        )
        assert skel.template_version == "skeleton_alt"
        assert "ALT TEMPLATE for Serum 50ml" in skel.deterministic_prompt

    def test_brand_override_wins_over_channel(self, brief, locale_profile, tmp_path):
        templates = tmp_path / "tpl"
        templates.mkdir()
        (templates / "skeleton_brand.j2").write_text(
            "BRAND TEMPLATE for {{ product_name }}\nAvoid: {{ avoid_list | join(', ') }}.",
        )
        (templates / "skeleton_alt.j2").write_text(
            "ALT TEMPLATE for {{ product_name }}\nAvoid: {{ avoid_list | join(', ') }}.",
        )
        cfg = default_prompt_config().model_copy(update={
            "templates_by_channel": {Channel.STORY_VERTICAL: "skeleton_alt"},
        })
        brand = BrandProfile(
            id="custom", name="Custom", version="1", voice="v",
            template_version="skeleton_brand",
        )
        composer = PromptComposer(config=cfg, template_dir=templates)
        skel = composer.build_skeleton(
            brief=brief, product=brief.products[0], channel=Channel.STORY_VERTICAL,
            brand=brand, locale_profile=locale_profile,
        )
        assert skel.template_version == "skeleton_brand"
        assert "BRAND TEMPLATE" in skel.deterministic_prompt

    def test_unknown_template_falls_back_to_default(self, brief, locale_profile):
        # Brand requests a template that doesn't exist on disk; composer
        # logs a warning and renders with the default instead.
        brand = BrandProfile(
            id="x", name="X", version="1", voice="v",
            template_version="does_not_exist",
        )
        composer = PromptComposer()
        skel = composer.build_skeleton(
            brief=brief, product=brief.products[0], channel=Channel.SOCIAL_FEED_SQUARE,
            brand=brand, locale_profile=locale_profile,
        )
        assert skel.template_version == "skeleton_v1"


class TestExternalTemplateDir:
    """External template_dir wins over bundled when both define a template."""

    def test_external_template_dir_overrides_bundled(self, brief, brand, locale_profile, tmp_path):
        external = tmp_path / "tpl"
        external.mkdir()
        (external / "skeleton_v1.j2").write_text(
            "EXTERNAL VERSION for {{ product_name }}.\n"
            "Avoid: {{ avoid_list | join(', ') }}.",
        )
        composer = PromptComposer(template_dir=external)
        skel = composer.build_skeleton(
            brief=brief, product=brief.products[0], channel=Channel.SOCIAL_FEED_SQUARE,
            brand=brand, locale_profile=locale_profile,
        )
        assert skel.deterministic_prompt.startswith("EXTERNAL VERSION")

    def test_missing_external_dir_falls_back_to_bundled(self, brief, brand, locale_profile):
        # Pointing at a non-existent dir is a no-op; bundled template still loads.
        composer = PromptComposer(template_dir=Path("/nope/does/not/exist"))
        skel = composer.build_skeleton(
            brief=brief, product=brief.products[0], channel=Channel.SOCIAL_FEED_SQUARE,
            brand=brand, locale_profile=locale_profile,
        )
        assert "Editorial product photograph of Serum 50ml" in skel.deterministic_prompt
