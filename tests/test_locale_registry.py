"""Tests for the YAML locale-profile loader."""

from __future__ import annotations

from pathlib import Path

from pipeline.locale.registry import LocaleRegistry, default_locale_profile


def _write(tmp: Path, name: str, body: str) -> None:
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / name).write_text(body, encoding="utf-8")


class TestLocaleRegistry:
    def test_loads_yaml_files(self, tmp_path):
        _write(tmp_path / "locales", "de-DE.yaml", """
locale: de-DE
language: German
cultural_cues: ["understated Berlin sensibility"]
seasonal_context: "Late spring."
aesthetic_keywords: ["matte finishes"]
forbidden_imagery: ["religious symbols"]
currency: EUR
units: metric
""".strip())
        reg = LocaleRegistry(profiles_dir=tmp_path / "locales")
        loc = reg.get("de-DE")
        assert loc.language == "German"
        assert "religious symbols" in loc.forbidden_imagery
        assert loc.currency == "EUR"
        assert loc.units == "metric"

    def test_unknown_locale_synthesizes_default(self, tmp_path, caplog):
        reg = LocaleRegistry(profiles_dir=tmp_path)
        loc = reg.get("xx-YY")
        assert loc.locale == "xx-YY"

    def test_no_dir_returns_synthesized_defaults(self, tmp_path):
        reg = LocaleRegistry(profiles_dir=tmp_path / "missing")
        assert reg.list_locales() == []
        assert reg.get("en-US").locale == "en-US"

    def test_default_profile_keeps_requested_tag(self):
        loc = default_locale_profile("ja-JP")
        assert loc.locale == "ja-JP"
