"""FastAPI entry point. Wires CORS, routers, and a health probe."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.deps import get_settings
from app.routes import assets, brands, campaigns

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="Creative Automation Pipeline",
    description="Brief-to-asset pipeline.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(campaigns.router)
app.include_router(assets.router)
app.include_router(brands.router)


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
