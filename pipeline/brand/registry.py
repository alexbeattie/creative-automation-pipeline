"""Eager YAML loader for BrandProfiles."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pipeline.models import BrandProfile

log = logging.getLogger(__name__)


def default_brand_profile() -> BrandProfile:
    return BrandProfile(
        id="default",
        name="Default",
        version="1.0.0",
        voice="Clean, modern, understated. Confident without exaggeration.",
        palette=[],
        must_include=["natural lighting", "clean staging"],
        must_avoid=["text in image", "watermarks", "competitor logos"],
        restricted_phrases=[],
        tone_examples=[],
    )


@dataclass(slots=True)
class BrandRegistry:
    profiles_dir: Path
    _profiles: dict[str, BrandProfile] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._profiles = {"default": default_brand_profile()}
        self.profiles_dir = Path(self.profiles_dir)
        if not self.profiles_dir.exists():
            log.info(
                "brand profiles_dir not found, using built-in default only: %s",
                self.profiles_dir,
            )
            return
        for path in sorted(self.profiles_dir.glob("*.yaml")):
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                profile = BrandProfile.model_validate(raw)
            except Exception:  # noqa: BLE001
                log.exception("failed to load brand profile: %s", path)
                continue
            if profile.id in self._profiles and profile.id != "default":
                log.warning("duplicate brand profile id %r in %s; overriding", profile.id, path)
            self._profiles[profile.id] = profile
            log.info("loaded brand profile %r v%s from %s", profile.id, profile.version, path.name)

    def get(self, brand_id: str) -> BrandProfile:
        if brand_id in self._profiles:
            return self._profiles[brand_id]
        log.warning("brand profile %r not found; falling back to 'default'", brand_id)
        return self._profiles["default"]

    def list_ids(self) -> list[str]:
        ids = list(self._profiles.keys())
        ids.sort(key=lambda i: (i != "default", i))
        return ids
