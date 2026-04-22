"""Tests for the Pydantic contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pipeline.models import Asset, AspectRatio, CampaignBrief, CampaignResult, Product


def _valid_product() -> Product:
    return Product(id="serum-50ml", name="Serum 50ml", description="A serum.")


def _valid_brief(**overrides) -> CampaignBrief:
    base = dict(
        campaign_name="C",
        target_region="US",
        target_audience="A",
        campaign_message="M",
        products=[_valid_product()],
    )
    base.update(overrides)
    return CampaignBrief(**base)


class TestAspectRatio:
    def test_native_pixels(self):
        assert AspectRatio.SQUARE.pixels == (1024, 1024)
        assert AspectRatio.PORTRAIT.pixels == (1024, 1536)
        assert AspectRatio.LANDSCAPE.pixels == (1536, 1024)

    def test_string_value_round_trip(self):
        assert AspectRatio("1:1") is AspectRatio.SQUARE
        assert AspectRatio("2:3") is AspectRatio.PORTRAIT
        assert AspectRatio("3:2") is AspectRatio.LANDSCAPE


class TestProduct:
    @pytest.mark.parametrize("bad_id", ["../evil", "with space", "UPPER", "", "with/slash"])
    def test_rejects_unsafe_ids(self, bad_id):
        with pytest.raises(ValidationError):
            Product(id=bad_id, name="x", description="x")

    def test_accepts_safe_ids(self):
        for ok in ["a", "a-b", "a_b", "sku-123", "hydration-serum-50ml"]:
            Product(id=ok, name="x", description="x")

    def test_strips_whitespace(self):
        p = Product(id="ok", name="  Name  ", description="  Desc  ")
        assert p.name == "Name"
        assert p.description == "Desc"


class TestCampaignBrief:
    def test_default_aspect_ratios_is_all_three(self):
        assert _valid_brief().aspect_ratios == list(AspectRatio)

    def test_aspect_ratios_dedupe_preserves_order(self):
        b = _valid_brief(aspect_ratios=[
            AspectRatio.PORTRAIT,
            AspectRatio.SQUARE,
            AspectRatio.PORTRAIT,
            AspectRatio.SQUARE,
        ])
        assert b.aspect_ratios == [AspectRatio.PORTRAIT, AspectRatio.SQUARE]

    def test_default_locale(self):
        assert _valid_brief().locale == "en-US"

    def test_locale_accepts_bcp47(self):
        for ok in ["en", "en-US", "de-DE", "ja-JP", "zh-Hant-TW"]:
            _valid_brief(locale=ok)

    def test_locale_rejects_garbage(self):
        with pytest.raises(ValidationError):
            _valid_brief(locale="!!")

    def test_idempotency_key_optional(self):
        assert _valid_brief().idempotency_key is None

    def test_idempotency_key_min_length(self):
        with pytest.raises(ValidationError):
            _valid_brief(idempotency_key="short")

    def test_at_least_one_product_required(self):
        with pytest.raises(ValidationError):
            CampaignBrief(
                campaign_name="C", target_region="US",
                target_audience="A", campaign_message="M", products=[],
            )


class TestAssetAndResult:
    def test_asset_rejects_absolute_path(self):
        with pytest.raises(ValidationError):
            Asset(
                product_id="p", aspect_ratio=AspectRatio.SQUARE,
                width=1024, height=1024, strategy="generated",
                relative_path="/etc/passwd",
            )

    def test_asset_rejects_parent_traversal(self):
        with pytest.raises(ValidationError):
            Asset(
                product_id="p", aspect_ratio=AspectRatio.SQUARE,
                width=1024, height=1024, strategy="generated",
                relative_path="../leaked",
            )

    def test_result_assigns_campaign_id(self):
        r = CampaignResult(campaign_name="C", assets=[])
        assert len(r.campaign_id) == 12
        # second result must get a different id
        r2 = CampaignResult(campaign_name="C", assets=[])
        assert r.campaign_id != r2.campaign_id
