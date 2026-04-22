"""Loads prompt_config.yaml into a typed PromptConfig with safe defaults."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from pipeline.models import Channel, PromptConfig

log = logging.getLogger(__name__)


def default_prompt_config() -> PromptConfig:
    return PromptConfig(
        default_template_version="skeleton_v1",
        templates_by_channel={},
        composition_by_channel={
            Channel.SOCIAL_FEED_SQUARE: (
                "balanced centered composition for social feed; subject fills "
                "the safe area"
            ),
            Channel.SOCIAL_FEED_PORTRAIT: (
                "vertical hero composition with the product offset slightly "
                "low for thumb-stop"
            ),
            Channel.STORY_VERTICAL: (
                "vertical full-bleed composition with clear headroom (top "
                "20%) and footer (bottom 20%) safe-areas for UI overlays"
            ),
            Channel.DISPLAY_LANDSCAPE: (
                "wide editorial composition with the subject left-of-center "
                "and negative space on the right"
            ),
            Channel.DISPLAY_BANNER: (
                "wide banner composition with strong horizontal eye-line and "
                "clean negative space on the right for headline overlay"
            ),
        },
        safety_directives=[
            "no text, captions, or watermarks rendered into the image",
            "no faces of identifiable real public figures",
            "no logos other than implied product packaging",
        ],
    )


def load_prompt_config(path: Path | None) -> PromptConfig:
    """Load prompt_config.yaml. Missing channels are back-filled from defaults."""
    base = default_prompt_config()
    if path is None or not path.exists():
        if path is not None:
            log.info("prompt_config.yaml not found at %s; using built-in defaults", path)
        return base

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        log.exception("failed to read prompt_config.yaml at %s; using defaults", path)
        return base

    merged: dict = base.model_dump()
    for key, value in raw.items():
        if value is None:
            continue
        merged[key] = value

    composition = dict(base.composition_by_channel)
    composition.update(merged.get("composition_by_channel") or {})
    merged["composition_by_channel"] = composition

    try:
        config = PromptConfig.model_validate(merged)
    except Exception:  # noqa: BLE001
        log.exception("prompt_config.yaml at %s failed validation; using defaults", path)
        return base

    missing = [c for c in Channel if c not in config.composition_by_channel]
    if missing:
        log.warning(
            "prompt_config.yaml is missing composition_by_channel for %s; "
            "back-filling from defaults",
            [c.value for c in missing],
        )
        for c in missing:
            config.composition_by_channel[c] = base.composition_by_channel[c]

    log.info("loaded prompt config from %s", path)
    return config
