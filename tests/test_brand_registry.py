"""Tests for the YAML brand-profile loader."""

from __future__ import annotations

from pathlib import Path

from pipeline.brand.registry import BrandRegistry, default_brand_profile


def _write(tmp: Path, name: str, body: str) -> None:
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / name).write_text(body, encoding="utf-8")


class TestBrandRegistry:
    def test_default_always_present(self, tmp_path):
        reg = BrandRegistry(profiles_dir=tmp_path / "missing")
        assert reg.get("default").id == "default"
        assert "default" in reg.list_ids()

    def test_loads_yaml_files(self, tmp_path):
        _write(tmp_path / "brands", "spring_glow.yaml", """
id: spring_glow
name: Spring Glow
version: 2026.04.01
voice: Warm and confident.
palette: ["#F4C7C3"]
must_include: ["natural daylight"]
must_avoid: ["medical claims"]
restricted_phrases: ["miracle"]
tone_examples: ["Less effort. More glow."]
""".strip())
        reg = BrandRegistry(profiles_dir=tmp_path / "brands")
        b = reg.get("spring_glow")
        assert b.name == "Spring Glow"
        assert b.version == "2026.04.01"
        assert b.palette == ["#F4C7C3"]
        assert "miracle" in b.restricted_phrases

    def test_unknown_id_falls_back_to_default(self, tmp_path):
        reg = BrandRegistry(profiles_dir=tmp_path)
        assert reg.get("does-not-exist").id == "default"

    def test_malformed_yaml_does_not_break_registry(self, tmp_path, caplog):
        _write(tmp_path / "brands", "bad.yaml", "id: bad\nname: : :\nversion:\n")
        _write(tmp_path / "brands", "good.yaml", """
id: good
name: Good
version: "1.0"
voice: ok
""".strip())
        reg = BrandRegistry(profiles_dir=tmp_path / "brands")
        assert reg.get("good").id == "good"
        # bad file did not register
        assert "bad" not in reg.list_ids()

    def test_default_profile_has_safe_defaults(self):
        b = default_brand_profile()
        assert b.id == "default"
        assert "text in image" in b.must_avoid
