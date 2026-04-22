"""Tests for the JSONL trace writer."""

from __future__ import annotations

import json

from pipeline.analytics.trace import (
    AssetTraceEvent,
    FilesystemTraceWriter,
    NoopTraceWriter,
)


def _evt(campaign_id: str = "c1", **overrides) -> AssetTraceEvent:
    base = dict(
        campaign_id=campaign_id,
        campaign_name="Camp",
        product_id="p",
        aspect_ratio="1:1",
        channel="social_feed_square",
        strategy="generated",
        brand_id="default",
        brand_version="1.0.0",
        locale="en-US",
        template_version="skeleton_v1",
        prompt_skeleton_hash="abc123",
        final_prompt="P",
        copy_source="user",
        copy_headline="Glow",
        latency_ms=1200,
        relative_path="c1/p/1-1.png",
        warnings=[],
    )
    base.update(overrides)
    return AssetTraceEvent(**base)


class TestNoopTraceWriter:
    async def test_does_nothing(self):
        writer = NoopTraceWriter()
        await writer.write(_evt())  # must not raise


class TestFilesystemTraceWriter:
    async def test_writes_one_jsonl_row(self, tmp_path):
        writer = FilesystemTraceWriter(base_dir=tmp_path)
        await writer.write(_evt())
        path = tmp_path / "c1" / "trace.jsonl"
        assert path.exists()
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(rows) == 1
        assert rows[0]["campaign_id"] == "c1"
        assert rows[0]["product_id"] == "p"
        assert rows[0]["latency_ms"] == 1200

    async def test_appends_multiple_rows(self, tmp_path):
        writer = FilesystemTraceWriter(base_dir=tmp_path)
        await writer.write(_evt(product_id="a"))
        await writer.write(_evt(product_id="b"))
        path = tmp_path / "c1" / "trace.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert [r["product_id"] for r in rows] == ["a", "b"]
