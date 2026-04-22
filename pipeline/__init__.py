"""Public surface of the pipeline package."""

from pipeline import models
from pipeline.models import CampaignBrief, CampaignResult
from pipeline.runner import PipelineRunner

__all__ = ["models", "CampaignBrief", "CampaignResult", "PipelineRunner", "run"]


async def run(brief: CampaignBrief, *, runner: PipelineRunner) -> CampaignResult:
    """Run a brief end-to-end. Runner is injected so the API and CLI can wire their own deps."""
    return await runner.run(brief)
