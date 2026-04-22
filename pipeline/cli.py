"""CLI entry point. Same pipeline as the API, no FastAPI required."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from pipeline.analytics.trace import FilesystemTraceWriter, NoopTraceWriter
from pipeline.brand.registry import BrandRegistry
from pipeline.copy.localizer import CopyLocalizer
from pipeline.locale.registry import LocaleRegistry
from pipeline.models import CampaignBrief
from pipeline.orchestrator import AssetOrchestrator
from pipeline.processing.image_processor import ImageProcessor
from pipeline.prompt.composer import PromptComposer
from pipeline.prompt.config import load_prompt_config
from pipeline.providers.openai_provider import OpenAIImageProvider
from pipeline.providers.openai_text import OpenAITextLLMProvider
from pipeline.runner import PipelineRunner
from pipeline.storage.filesystem import FilesystemStorage


def _truthy(s: str | None) -> bool:
    return (s or "").strip().lower() in {"1", "true", "yes", "on"}


def _build_runner() -> PipelineRunner:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    image_timeout_seconds = float(os.environ.get("OPENAI_IMAGE_TIMEOUT_SECONDS", "120"))
    image_max_retries = int(os.environ.get("OPENAI_IMAGE_MAX_RETRIES", "3"))
    output_dir = Path(os.environ.get("OUTPUT_DIR", "./output"))
    brand_dir = Path(os.environ.get("BRAND_PROFILES_DIR", "./brand_profiles"))
    locale_dir = Path(os.environ.get("LOCALE_PROFILES_DIR", "./locale_profiles"))
    prompt_templates_dir = Path(os.environ.get("PROMPT_TEMPLATES_DIR", "./prompt_templates"))
    prompt_config_path = Path(os.environ.get("PROMPT_CONFIG_PATH", "./prompt_config.yaml"))

    enable_copy = _truthy(os.environ.get("ENABLE_COPY_LOCALIZATION", "1"))
    enable_trace = _truthy(os.environ.get("ENABLE_TRACE_WRITER", "1"))

    text_llm = (
        OpenAITextLLMProvider(api_key=api_key)
        if api_key and enable_copy
        else None
    )

    composer = PromptComposer(
        config=load_prompt_config(prompt_config_path),
        template_dir=prompt_templates_dir,
    )
    localizer = CopyLocalizer(text_llm=text_llm) if enable_copy and text_llm else None
    trace_writer = FilesystemTraceWriter(base_dir=output_dir) if enable_trace else NoopTraceWriter()

    orchestrator = AssetOrchestrator(
        brand_registry=BrandRegistry(profiles_dir=brand_dir),
        locale_registry=LocaleRegistry(profiles_dir=locale_dir),
        composer=composer,
    )

    return PipelineRunner(
        provider=OpenAIImageProvider(
            api_key=api_key,
            timeout_seconds=image_timeout_seconds,
            max_retries=image_max_retries,
        ),
        processor=ImageProcessor(),
        storage=FilesystemStorage(base_dir=output_dir),
        orchestrator=orchestrator,
        localizer=localizer,
        trace_writer=trace_writer,
    )


async def _run(brief_path: Path) -> int:
    brief_text = brief_path.read_text()  # noqa: ASYNC240
    brief = CampaignBrief.model_validate_json(brief_text)
    runner = _build_runner()
    result = await runner.run(brief)
    sys.stdout.write(result.model_dump_json(indent=2))
    sys.stdout.write("\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipeline-cli")
    parser.add_argument("brief", type=Path, help="Path to a CampaignBrief JSON file.")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable INFO-level logging.",
    )
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(_run(args.brief)))


if __name__ == "__main__":
    main()
