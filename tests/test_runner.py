"""End-to-end runner tests using fakes."""

from __future__ import annotations

import pytest

from pipeline.models import AspectRatio, CampaignBrief, Product
from pipeline.providers.base import GenAIProvider
from pipeline.runner import PipelineRunner


@pytest.fixture
def runner(fake_provider, fake_processor, storage) -> PipelineRunner:
    return PipelineRunner(provider=fake_provider, processor=fake_processor, storage=storage)


class TestProtocolConformance:
    def test_fake_provider_satisfies_protocol(self, fake_provider):
        assert isinstance(fake_provider, GenAIProvider)


class TestEndToEnd:
    async def test_cropped_branch_produces_all_assets(self, runner, brief_with_source, fake_provider):
        result = await runner.run(brief_with_source)
        assert len(result.assets) == 3  # 1 product x 3 ratios
        assert result.warnings == []
        assert all(a.strategy == "cropped" for a in result.assets)
        assert fake_provider.calls == []  # no AI calls when cropping

    async def test_each_asset_has_correct_native_size(self, runner, brief_with_source):
        result = await runner.run(brief_with_source)
        sizes = {a.aspect_ratio: (a.width, a.height) for a in result.assets}
        assert sizes[AspectRatio.SQUARE]    == (1024, 1024)
        assert sizes[AspectRatio.PORTRAIT]  == (1024, 1536)
        assert sizes[AspectRatio.LANDSCAPE] == (1536, 1024)

    async def test_files_actually_written_to_disk(self, runner, brief_with_source, storage, tmp_path):
        result = await runner.run(brief_with_source)
        for asset in result.assets:
            abs_path = storage.absolute_path(asset.relative_path)
            assert abs_path.exists()
            assert abs_path.stat().st_size > 0
            # Files live under the configured output dir, never above it.
            assert str(abs_path).startswith(str((tmp_path / "output").resolve()))


class TestIdempotency:
    async def test_repeat_with_same_key_returns_cached_result(self, runner, brief_with_source):
        brief_with_source = brief_with_source.model_copy(update={"idempotency_key": "abcd1234ef"})
        first = await runner.run(brief_with_source)
        second = await runner.run(brief_with_source)
        assert first.campaign_id == second.campaign_id
        assert [a.relative_path for a in first.assets] == [a.relative_path for a in second.assets]

    async def test_no_key_means_no_caching(self, runner, brief_with_source):
        first = await runner.run(brief_with_source)
        second = await runner.run(brief_with_source)
        assert first.campaign_id != second.campaign_id


class TestPartialFailure:
    async def test_one_failed_plan_does_not_kill_the_run(self, fake_processor, storage):
        from tests.conftest import FakeProvider
        provider = FakeProvider(fail_on_prompt_substring="BrokenSKU")
        runner = PipelineRunner(provider=provider, processor=fake_processor, storage=storage)

        brief = CampaignBrief(
            campaign_name="C", target_region="US",
            target_audience="A", campaign_message="M",
            products=[
                Product(id="ok-sku", name="OK", description="works",
                        source_image_path=__file__),     # cropped path
                Product(id="broken-sku", name="BrokenSKU", description="boom"),  # generated path, will fail
            ],
            aspect_ratios=[AspectRatio.SQUARE],
        )
        result = await runner.run(brief)

        assert len(result.assets) == 1
        assert result.assets[0].product_id == "ok-sku"
        assert len(result.warnings) == 1
        assert "broken-sku" in result.warnings[0]
