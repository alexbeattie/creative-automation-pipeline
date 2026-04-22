# Creative Automation Pipeline

This repository contains a local proof-of-concept creative automation pipeline for scalable social campaigns. It accepts a structured campaign brief plus optional source assets, reuses approved imagery when available, generates missing imagery with `gpt-image-1`, overlays campaign messaging, and saves finished outputs plus trace logs locally.

## Demo

- Public repository: [alexbeattie/creative-automation-pipeline](https://github.com/alexbeattie/creative-automation-pipeline)
- Demo video: add your 2-3 minute screencast link here before submission

## Quick Start

1. Copy the environment file and set `OPENAI_API_KEY`.

```bash
cp .env.example .env
```

2. Create a Python virtual environment, install dependencies, and start the FastAPI backend.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

3. In a second terminal, start the Vue frontend.

```bash
cd ui
npm install
npm run dev
```

4. Open `http://localhost:5173`.

If Vite chooses a different port, update `CORS_ORIGIN` in `.env` to match and restart the backend.

It is built around a simple operating rule:

- if a product already has approved source imagery, reuse it
- if a product is missing imagery, generate it with `gpt-image-1`

From there, the pipeline applies brand guidance, locale context, ratio- or channel-specific composition rules, optional copy localization, and a consistent output manifest that the UI can render directly.

## What The System Does

Given a campaign brief, the pipeline will:

1. resolve the requested brand profile and locale profile
2. expand the brief into one asset plan per product and ratio or channel
3. decide whether each asset should be `cropped` or `generated`
4. build a deterministic image prompt for generated assets
5. optionally localize the campaign message for the selected locale
6. generate or crop the raw image
7. apply the text overlay
8. write the finished PNG to disk
9. return a manifest describing the run and every produced asset

The result is a workflow that is AI-enabled where it matters, but still explicit and inspectable at every step.

## Core Behavior

### Asset Strategy

The orchestrator makes one decision per asset plan:

- `cropped` if `product.source_image_path` is available
- `generated` if it is not

That decision lives in [`pipeline/orchestrator.py`](./pipeline/orchestrator.py) and is intentionally simple. The point of the prototype is not to invent complex heuristics; it is to demonstrate a credible creative-operations flow with clear reuse-vs-generation behavior.

### Prompt Composition

Generated assets use a deterministic prompt composer in [`pipeline/prompt/composer.py`](./pipeline/prompt/composer.py).

The prompt is assembled from:

- product metadata
- campaign audience and region
- brand voice, palette, and must-avoid guidance
- locale aesthetic and cultural cues
- channel-specific composition directives
- always-on safety directives

Prompt structure is versioned through Jinja templates in `prompt_templates/` and config in `prompt_config.yaml`.

### Copy Localization

Overlay copy is handled once per campaign in [`pipeline/copy/localizer.py`](./pipeline/copy/localizer.py).

Behavior is:

- English locales use the typed `campaign_message` directly
- non-English locales can call a text model to adapt the message
- if localization is disabled or unavailable, the pipeline falls back to the original message

### Idempotency

The runner keeps a process-local idempotency cache in [`pipeline/runner.py`](./pipeline/runner.py).

If `idempotency_key` is supplied, repeat submissions with the same key, brand version, and locale return the cached `CampaignResult` instead of rerunning generation. This is meant to protect against retries and double-submits during long runs.

### Storage And Trace

Finished assets are written under `OUTPUT_DIR` using deterministic relative paths:

```text
<OUTPUT_DIR>/<campaign_id>/<product_id>/<aspect_label>.png
```

Example:

```text
./output/a1b2c3d4e5f6/hydration-serum/1-1.png
```

The pipeline can also append one JSONL trace row per asset for later analysis.

## HTTP API

The FastAPI app in [`app/main.py`](./app/main.py) exposes five routes:

- `GET /api/health`
- `GET /api/brands`
- `GET /api/locales`
- `POST /api/campaigns`
- `GET /api/assets/{relative_path}`

### `POST /api/campaigns`

This endpoint accepts `multipart/form-data` so the brief and optional source images can be submitted together.

Form fields:

- `brief`: JSON-serialized `CampaignBrief`
- `sources`: zero or more uploaded files, in product order

The API persists uploaded files to a temporary directory under `OUTPUT_DIR/_uploads/`, rewrites each matching product's `source_image_path`, and then passes the parsed brief to the runner. The pipeline core never deals with HTTP directly.

### Example Brief

The JSON inside the `brief` field looks like this:

```json
{
  "campaign_name": "Spring Glow 2026",
  "target_region": "EU-DE",
  "locale": "de-DE",
  "brand_profile_id": "spring_glow",
  "target_audience": "Berlin commuters, skincare-conscious, 25-40",
  "campaign_message": "Glow Like Never Before",
  "products": [
    {
      "id": "hydration-serum",
      "name": "Hydration Serum",
      "description": "Lightweight hyaluronic-acid serum."
    }
  ],
  "aspect_ratios": ["1:1", "2:3", "3:2"],
  "idempotency_key": "spring-glow-2026-de-serum-v1"
}
```

Notes:

- `source_image_path` is not normally included in API briefs; uploaded files are attached separately as `sources`
- if `channels` is supplied, it replaces `aspect_ratios` as the expansion axis
- the current UI uses `aspect_ratios`, but the backend contract supports both

### Response Shape

`POST /api/campaigns` returns a `CampaignResult` with:

- `campaign_id`
- `campaign_name`
- `brand_profile_id`
- `brand_profile_version`
- `created_at`
- `assets[]`
- `warnings[]`

Each asset includes:

- `product_id`
- `aspect_ratio`
- `channel`
- `width`
- `height`
- `strategy`
- `relative_path`
- `prompt`
- `copy`
- `prompt_trace`

The UI uses `relative_path` to request the final image from `/api/assets/...`.

## Profiles And Prompt Files

### Brand Profiles

Brand profiles are YAML files loaded from `brand_profiles/` by [`pipeline/brand/registry.py`](./pipeline/brand/registry.py).

They control:

- brand name and version
- voice and palette
- required visual cues
- banned visuals or phrases
- optional template override

### Locale Profiles

Locale profiles are YAML files loaded from `locale_profiles/` by [`pipeline/locale/registry.py`](./pipeline/locale/registry.py).

They control:

- display language
- cultural cues
- seasonal context
- aesthetic keywords
- forbidden imagery

### Prompt Templates

Prompt templates live in `prompt_templates/`.

`prompt_config.yaml` defines:

- the default template version
- per-channel template overrides
- per-channel composition directives
- always-on safety directives

This keeps prompt shape editable without pushing prompt text down into the runner or API layers.

## Repository Layout

- [`app`](./app): FastAPI transport layer
- [`pipeline/models.py`](./pipeline/models.py): typed request/response and profile contracts
- [`pipeline/orchestrator.py`](./pipeline/orchestrator.py): asset planning and crop-vs-generate decision
- [`pipeline/prompt`](./pipeline/prompt): deterministic prompt composition
- [`pipeline/runner.py`](./pipeline/runner.py): async execution, localization, persistence, trace writing, idempotency
- [`pipeline/processing`](./pipeline/processing): image crop and overlay operations
- [`pipeline/copy`](./pipeline/copy): localized copy adaptation
- [`pipeline/storage`](./pipeline/storage): filesystem-backed asset storage
- [`ui`](./ui): Vue demo client
- [`tests`](./tests): unit and integration coverage

## Running Locally

### Python

Create a virtual environment, install the package, and run the API:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

### Frontend

```bash
cd ui
npm install
npm run dev
```

### CLI

The CLI hits the same pipeline core without going through FastAPI:

```bash
pipeline-cli brief.json
```

## Environment Variables

The main runtime settings are documented in [`.env.example`](./.env.example).

The most important ones are:

- `OPENAI_API_KEY`
- `OPENAI_IMAGE_TIMEOUT_SECONDS`
- `OPENAI_IMAGE_MAX_RETRIES`
- `OUTPUT_DIR`
- `CORS_ORIGIN`
- `BRAND_PROFILES_DIR`
- `LOCALE_PROFILES_DIR`
- `PROMPT_TEMPLATES_DIR`
- `PROMPT_CONFIG_PATH`
- `ENABLE_COPY_LOCALIZATION`
- `ENABLE_TRACE_WRITER`

## Tests

Backend:

```bash
.venv/bin/pytest
```

Frontend:

```bash
cd ui
npm run build
```

## Constraints And Next Steps

Current constraints:

- idempotency is process-local, not shared across instances
- assets are stored on the local filesystem
- the UI currently exposes ratio-based generation, while the backend contract also supports channels
- generation is pinned to the native `gpt-image-1` sizes defined in `AspectRatio`

The next practical extensions would be shared cache/storage, richer channel handling in the UI, and downstream analytics that consume the JSONL trace.
