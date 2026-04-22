"""Tests for pipeline.prompt.config.load_prompt_config."""

from __future__ import annotations

from pathlib import Path

from pipeline.models import Channel
from pipeline.prompt.config import default_prompt_config, load_prompt_config


class TestDefaults:
    def test_default_covers_all_channels(self):
        cfg = default_prompt_config()
        for c in Channel:
            assert c in cfg.composition_by_channel
            assert cfg.composition_by_channel[c].strip()

    def test_default_has_safety_directives(self):
        cfg = default_prompt_config()
        assert cfg.safety_directives
        assert any("text" in s.lower() for s in cfg.safety_directives)

class TestFileLoading:
    def test_no_path_returns_defaults(self):
        cfg = load_prompt_config(None)
        assert cfg.default_template_version == "skeleton_v1"

    def test_missing_path_returns_defaults(self, tmp_path):
        cfg = load_prompt_config(tmp_path / "nope.yaml")
        assert cfg.composition_by_channel == default_prompt_config().composition_by_channel

    def test_malformed_yaml_returns_defaults(self, tmp_path):
        bad = tmp_path / "prompt_config.yaml"
        bad.write_text("this: is: not: valid: yaml: [")
        cfg = load_prompt_config(bad)
        assert cfg.default_template_version == default_prompt_config().default_template_version

    def test_partial_override_merges_with_defaults(self, tmp_path):
        path = tmp_path / "prompt_config.yaml"
        path.write_text(
            "safety_directives:\n"
            "  - custom safety rule\n"
            "  - no nudity\n"
        )
        cfg = load_prompt_config(path)
        assert cfg.safety_directives == ["custom safety rule", "no nudity"]
        assert cfg.default_template_version == "skeleton_v1"
        for c in Channel:
            assert c in cfg.composition_by_channel

    def test_partial_channel_override_backfills_missing_channels(self, tmp_path):
        path = tmp_path / "prompt_config.yaml"
        path.write_text(
            "composition_by_channel:\n"
            "  story_vertical: 'custom story directive'\n"
        )
        cfg = load_prompt_config(path)
        assert cfg.composition_by_channel[Channel.STORY_VERTICAL] == "custom story directive"
        for c in Channel:
            assert cfg.composition_by_channel[c]

    def test_template_overrides_load_correctly(self, tmp_path):
        path = tmp_path / "prompt_config.yaml"
        path.write_text(
            "default_template_version: skeleton_v2\n"
            "templates_by_channel:\n"
            "  story_vertical: skeleton_story_v1\n"
            "  display_banner: skeleton_banner_v1\n"
        )
        cfg = load_prompt_config(path)
        assert cfg.default_template_version == "skeleton_v2"
        assert cfg.templates_by_channel[Channel.STORY_VERTICAL] == "skeleton_story_v1"
        assert cfg.templates_by_channel[Channel.DISPLAY_BANNER] == "skeleton_banner_v1"

    def test_seeded_repo_yaml_loads(self):
        repo_root = Path(__file__).resolve().parents[1]
        seed = repo_root / "prompt_config.yaml"
        if not seed.exists():
            return
        cfg = load_prompt_config(seed)
        for c in Channel:
            assert cfg.composition_by_channel[c]
        assert cfg.safety_directives
