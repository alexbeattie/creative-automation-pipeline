"""GET /api/brands and /api/locales. Read-only registry projections for the UI."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_brand_registry, get_locale_registry
from pipeline.brand.registry import BrandRegistry
from pipeline.locale.registry import LocaleRegistry
from pipeline.models import BrandProfile, LocaleProfile

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/brands", response_model=list[BrandProfile])
async def list_brands(
    registry: BrandRegistry = Depends(get_brand_registry),
) -> list[BrandProfile]:
    return [registry.get(bid) for bid in registry.list_ids()]


@router.get("/locales", response_model=list[LocaleProfile])
async def list_locales(
    registry: LocaleRegistry = Depends(get_locale_registry),
) -> list[LocaleProfile]:
    return [registry.get(loc) for loc in registry.list_locales()]
