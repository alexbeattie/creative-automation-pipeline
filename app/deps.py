"""Settings and dependency injection for the FastAPI app."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from pipeline.analytics.trace import FilesystemTraceWriter, NoopTraceWriter, TraceWriter
from pipeline.brand.registry import BrandRegistry
from pipeline.copy.localizer import CopyLocalizer
from pipeline.locale.registry import LocaleRegistry
from pipeline.orchestrator import AssetOrchestrator
from pipeline.processing.image_processor import ImageProcessor
from pipeline.prompt.composer import PromptComposer
from pipeline.prompt.config import PromptConfig, load_prompt_config
from pipeline.providers.openai_provider import OpenAIImageProvider
from pipeline.providers.openai_text import OpenAITextLLMProvider
from pipeline.runner import PipelineRunner
from pipeline.storage.filesystem import FilesystemStorage


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    openai_image_timeout_seconds: float = 120.0
    openai_image_max_retries: int = 3
    output_dir: Path = Path("./output")
    log_level: str = "INFO"
    cors_origin: str = "http://localhost:5173"

    brand_profiles_dir: Path = Path("./brand_profiles")
    locale_profiles_dir: Path = Path("./locale_profiles")

    prompt_templates_dir: Path = Path("./prompt_templates")
    prompt_config_path: Path = Path("./prompt_config.yaml")

    enable_copy_localization: bool = True
    enable_trace_writer: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_brand_registry() -> BrandRegistry:
    return BrandRegistry(profiles_dir=get_settings().brand_profiles_dir)


@lru_cache
def get_locale_registry() -> LocaleRegistry:
    return LocaleRegistry(profiles_dir=get_settings().locale_profiles_dir)


@lru_cache
def get_prompt_config() -> PromptConfig:
    return load_prompt_config(get_settings().prompt_config_path)


@lru_cache
def get_runner() -> PipelineRunner:
    s = get_settings()
    text_llm = (
        OpenAITextLLMProvider(api_key=s.openai_api_key)
        if s.openai_api_key and s.enable_copy_localization
        else None
    )

    composer = PromptComposer(
        config=get_prompt_config(),
        template_dir=s.prompt_templates_dir,
    )
    localizer = (
        CopyLocalizer(text_llm=text_llm) if s.enable_copy_localization and text_llm else None
    )
    trace_writer: TraceWriter = (
        FilesystemTraceWriter(base_dir=s.output_dir) if s.enable_trace_writer else NoopTraceWriter()
    )

    orchestrator = AssetOrchestrator(
        brand_registry=get_brand_registry(),
        locale_registry=get_locale_registry(),
        composer=composer,
    )

    return PipelineRunner(
        provider=OpenAIImageProvider(
            api_key=s.openai_api_key,
            timeout_seconds=s.openai_image_timeout_seconds,
            max_retries=s.openai_image_max_retries,
        ),
        processor=ImageProcessor(),
        storage=FilesystemStorage(base_dir=s.output_dir),
        orchestrator=orchestrator,
        localizer=localizer,
        trace_writer=trace_writer,
    )
