"""Eager YAML loader for LocaleProfiles."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pipeline.models import LocaleProfile

log = logging.getLogger(__name__)


def default_locale_profile(locale: str = "en-US") -> LocaleProfile:
    return LocaleProfile(
        locale=locale,
        language="English" if locale.lower().startswith("en") else locale,
        cultural_cues=[],
        seasonal_context="",
        aesthetic_keywords=["clean", "modern"],
        forbidden_imagery=[],
        currency="",
        units="",
    )


@dataclass(slots=True)
class LocaleRegistry:
    profiles_dir: Path
    _profiles: dict[str, LocaleProfile] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._profiles = {}
        self.profiles_dir = Path(self.profiles_dir)
        if not self.profiles_dir.exists():
            log.info(
                "locale profiles_dir not found, using built-in defaults: %s",
                self.profiles_dir,
            )
            return
        for path in sorted(self.profiles_dir.glob("*.yaml")):
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                profile = LocaleProfile.model_validate(raw)
            except Exception:  # noqa: BLE001
                log.exception("failed to load locale profile: %s", path)
                continue
            self._profiles[profile.locale] = profile
            log.info("loaded locale profile %r from %s", profile.locale, path.name)

    def get(self, locale: str) -> LocaleProfile:
        if locale in self._profiles:
            return self._profiles[locale]
        log.warning("locale profile %r not found; synthesizing neutral default", locale)
        return default_locale_profile(locale)

    def list_locales(self) -> list[str]:
        return sorted(self._profiles.keys())
