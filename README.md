# 📸 DailyFX for Immich

### *Turn your static photo library into a dynamic, AI-powered creative playground.*

**DailyFX** is a self-hosted creative companion designed specifically for [Immich](https://immich.app). It breathes new life into your photo archives by automatically transforming your pictures into stunning artistic masterpieces—from vintage film strips and pop-art collages to next-gen AI-generated transformations. Review them daily, approve your favorites with one click, and seamlessly upload them back to Immich with all original EXIF metadata (camera, GPS, and timestamp) perfectly preserved.

Unlike generic photo filters that strip away metadata or require tedious manual work, DailyFX acts as an automated background curator. It connects directly to your Immich instance, retrieves assets based on your custom schedules, and applies any of its 40+ built-in creative modules. You can choose classic darkroom simulations like Cyanotype and Polaroid, high-dynamic-range enhancements, or leverage state-of-the-art Generative AI models to reimagine your photos in comic book, cyberpunk, or claymation styles.

The entire process is designed with the self-hoster in mind. Running completely on your own hardware via Docker, it ensures your private memories never leave your control. It features a metadata pipeline that supports AI-powered caption and title generation (via OpenAI, Gemini, OpenRouter, BytePlus, or Xiaomi), automatically analyzing the final image so the stored title, summary, and tags match what you actually review.

Once an effect is generated, you are notified through your preferred channel, whether that is an interactive Telegram message, a Home Assistant alert, a Gotify/ntfy notification, or a standard Web Push. With a single tap from the notification, you can compare the original and styled version, then choose to upload it back to Immich or discard it completely. For a concise run-through of the workflow, see [docs/how-it-works.md](docs/how-it-works.md).

> ⚖️ **License:** Source-available under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/). Free for personal and non-commercial use.

---

## Features

| Effect | Description |
|---|---|
| **Collage** | Four-filter collage with enhanced borders and depth |
| **Instafilter** | Single-photo Instagram-style filter |
| **Filmstrip** | Retro filmstrip layout with date and time labels |
| **Pop Art** | Bold four-tile pop-art with vivid Warhol-style colors |
| **Duotone** | Rich duotone grading with depth and texture |
| **Halftone** | Artistic halftone with varied dot sizes and depth |
| **Glitch** | RGB channel shifts, scanlines, and horizontal distortion |
| **Light Leak** | Warm film leaks with faded blacks and dreamy glow |
| **Neon Bloom** | Vivid bloom with glowing highlights and neon saturation |
| **Cyanotype** | Blue-print toning with paper texture and adjustable tone |
| **Polaroid** | Classic instant-film frame with high-legibility typography |
| **Prism Split** | Bold chromatic aberration with prismatic color split |
| **Paper Cutout** | Layered paper cutout with rich texture and depth |
| **Museum Archive** | Fine-art gallery framing with elegant serif typography and passe-partout |
| **Bokeh Blur** | Professional depth of field with face detection |
| **Vintage Film** | Authentic film stock with S-curve tone mapping |
| **Huji Cam** | Disposable film camera look — warm tones, light leaks, grain and date stamp |
| **Pencil Sketch** | Hand-drawn pencil sketch using OpenCV |
| **Cartoon** | Cartoon effect with bold edges and flat colors |
| **HDR** | HDR tone mapping with vivid colors and enhanced dynamic range |
| **AI Anime** | AI-generated anime-style art *(requires AI provider API key)* |
| **AI Caricature** | AI-generated caricature *(requires AI provider API key)* |
| **AI Comic Book** | AI-generated retro comic book illustration *(requires AI provider API key)* |
| **AI Cyberpunk** | AI-generated neon-soaked cyberpunk artwork *(requires AI provider API key)* |
| **AI Claymation** | AI-generated plasticine stop-motion clay art *(requires AI provider API key)* |
| **AI Cinematic 3D Toy** | AI-generated polished cinematic 3D toy-style portrait *(requires AI provider API key)* |
| **AI Collectible Hero Figure** | AI-generated premium collectible hero figure portrait *(requires AI provider API key)* |
| **AI Fantasy Hero** | AI-generated epic fantasy portrait *(requires AI provider API key)* |
| **AI High-Fashion Editorial** | AI-generated luxury editorial portrait *(requires AI provider API key)* |
| **AI Brick-Built Figure** | AI-generated playful brick-built character scene *(requires AI provider API key)* |
| **AI Yellow Cartoon Sitcom** | AI-generated bright cartoon family-comedy portrait *(requires AI provider API key)* |

**Workflow:**
1. Scheduler picks a weighted random effect and fetches photos from your Immich library
2. Generated image appears in the web UI for review
3. **Accept** → uploads to Immich with original EXIF (date, camera, GPS, etc.) and adds to album
4. **Reject** → logged in history, not uploaded

**Other features:**
- Push notifications (Web Push, ntfy, Gotify, Telegram Bot, Home Assistant) with image preview
- Mobile-friendly review page linked from notification
- Per-effect enable/disable and weight
- Filter by Immich album, person, date range, media type
- Schedules: daily, specific days, time of day
- Optional AI vision analysis (via OpenAI, Gemini, OpenRouter, BytePlus, or Xiaomi) for titles and captions; for `ai_*` effects, the final generated image is analyzed again so the stored title, summary, and tags match the result you actually review. See `docs/api.md` for the metadata pipeline, including `metadata_provenance`, `people_context`, `task_trace`, and **API Rate Limits**.
For API-key setup links, see [docs/api.md](docs/api.md#ai-provider-key-setup).

---

## Requirements

- Docker and Docker Compose
- A running [Immich](https://immich.app) instance

---

## Quick start

There are two ways to run DailyFX: using pre-built images from GitHub Container Registry (recommended), or building from source.

### Option A: Running Pre-built Images (Recommended)

You do not need to clone the repository to run DailyFX. You can run it directly using Docker Compose:

1. Create a `docker-compose.yml` file in an empty directory. You can choose either a minimal version or a production-ready version with healthchecks and limits:

#### Minimal Version

```yaml
services:
  api:
    image: ghcr.io/ferges123/dailyfx-api:latest
    restart: unless-stopped
    user: "${UID:-1000}:${GID:-1000}"
    env_file: .env
    volumes:
      - ./data:/data
    ports:
      - "127.0.0.1:8438:8438"

  web:
    image: ghcr.io/ferges123/dailyfx-web:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:8439:8080"
```

#### Production-Ready Version (with healthchecks & limits)

```yaml
services:
  api:
    image: ghcr.io/ferges123/dailyfx-api:latest
    restart: unless-stopped
    user: "${UID:-1000}:${GID:-1000}"
    env_file: .env
    volumes:
      - ./data:/data
    ports:
      - "127.0.0.1:8438:8438"
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    mem_limit: 2g
    cpus: 2.0
    healthcheck:
      test: ["CMD", "python", "healthcheck.py"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s

  web:
    image: ghcr.io/ferges123/dailyfx-web:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:8439:8080"
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    mem_limit: 512m
    cpus: 1.0
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:8080/"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    depends_on:
      api:
        condition: service_healthy
```

2. Create a `.env` file next to your `docker-compose.yml` and add a secure random key:

```env
APP_SECRET_KEY=    # generate with: openssl rand -hex 32
```

3. Start the containers:

```bash
docker compose up -d
```

---

### Option B: Building from Source

If you want to clone the repository and build the images locally:

1. Clone the repository and copy `.env.example`:
```bash
git clone https://github.com/ferges123/dailyFX.git
cd dailyFX
cp .env.example .env
```

2. Edit `.env` to generate a secure secret key:
```env
APP_SECRET_KEY=    # generate with: openssl rand -hex 32
```

3. Build and start:
```bash
docker compose up --build -d
```

---

Open **http://localhost:8439** in your browser. Go to the **Settings** tab to configure your Immich URL and API Key, plus any optional AI API keys (OpenAI, Gemini, OpenRouter, BytePlus, or Xiaomi).

If you want the simplest walkthrough, start with [docs/getting-started.md](docs/getting-started.md). For the short operator flow summary, see [docs/how-it-works.md](docs/how-it-works.md). If you want the full deployment guide, see [docs/self-hosting.md](docs/self-hosting.md).

### Local backend tooling

Use the repository `Makefile` for backend commands so you do not depend on global `python` or `pytest` being on your PATH:

```bash
make backend-install
make backend-test
```

`backend-test` runs `python3 -m pytest` inside `backend/`.

---

## Configuration

All connections (Immich, AI keys) and preferences are configured directly via the web UI (**Settings** and **Presets** tabs). The `.env` file is only used for system-level configuration at startup.

### `.env` reference

| Variable | Required | Description |
|---|---|---|
| `APP_SECRET_KEY` | **yes** | Random secret used to encrypt stored API keys. Generate with `openssl rand -hex 32`. |
| `APP_ENV` | no | Application environment (`production` or `development`, default: `development`). |
| `APP_HOST` | no | Host binding address (default: `0.0.0.0`). |
| `APP_PORT` | no | Backend API port (default: `8438`). |
| `DATA_DIR` | no | Directory for SQLite DB, results, and caches (default: `./data`). |
| `DATABASE_URL` | no | Database connection string (default: `sqlite:///./data/app.db`). |
| `APP_ACCESS_TOKEN` | no | If set, all API endpoints require `Authorization: Bearer <token>`. Recommended for internet-exposed instances. |
| `REQUIRE_AUTH_FOR_REVIEW` | no | If set to `true`, history review and image endpoints will also require auth (default: `false`). |
| `APP_EXTERNAL_URL` | no | Public/External URL of your DailyFX instance (required for images and action buttons in notifications). |
| `APP_CONTACT_EMAIL` | no | Email to contact the administrator (default: `dailyfx@localhost`). |
| `EXAMPLE_ASSET_ID` | no | Any asset ID from your library — enables effect preview images in the Effects tab. |
| `CORS_ORIGINS` | no | Comma-separated allowed origins (default: localhost and frontend ports). |

> [!NOTE]
> Immich connection details (`IMMICH_URL` and `IMMICH_API_KEY`), AI API keys, and notification integrations are managed dynamically in the web UI settings/presets instead of the `.env` file.

### Ports

| Port | Service |
|---|---|
| `8439` | Web UI (nginx) |
| `8438` | Backend API |

To change ports, edit `docker-compose.yml`.

---

## Automation

Set up schedules in the **Schedules** tab:

- Daily at a specific time
- Specific days of the week
- With optional source filters (album, people, date range)

The scheduler runs inside the backend container. If automation is disabled, you can still trigger a selected schedule manually with the **Run now** button in the **Schedules** tab.
Manual `Run now` requests are added to History immediately as `Queued`, then switch to `Running` when the worker starts processing them.
For a practical explanation of what happens after a schedule fires, see [docs/how-it-works.md](docs/how-it-works.md).

---

## Notifications

Notification channels can be configured in the **Notifications** tab (on desktop) or under **Presets** -> **Notifications** (on mobile).

### Web Push
Subscribe from the browser on the Settings or Notifications page. Notifications include a preview of the generated image with a direct link to the review page.

### ntfy
Set your ntfy server URL, topic name, and optional token. When `APP_EXTERNAL_URL` is configured, DailyFX also attaches the generated image and a click target back to the review page.

### Gotify
Set your Gotify server URL and app token.

### Telegram Bot
Get interactive notifications with action buttons (Accept & Upload / Reject) directly on your phone. See the [Telegram Setup Guide](docs/telegram_setup.md) for details.

### Home Assistant
Send notifications to Home Assistant via REST API. Supports push notifications (via mobile app services) and persistent sidebar notifications. See the [Home Assistant Setup Guide](docs/home_assistant_setup.md) for details.

---

## Adding a custom effect

1. Create `backend/app/services/generation/modules/myeffect.py`:

```python
from app.models.settings import SettingsModel
from app.services.generation.modules.base import GenerationResult

class MyEffectModule:
    name = "my_effect"
    label = "My Effect"
    description = "Does something cool."
    default_weight = 1
    default_config = {}
    config_schema = []

    async def run(self, page_items, config, client, settings: SettingsModel) -> GenerationResult:
        asset = page_items[0]
        image_bytes, _ = await client.get_asset_thumbnail(asset.id, size="preview")
        # ... process image_bytes ...
        return GenerationResult(
            title=f"My Effect: {asset.original_file_name}",
            summary="Applied my custom effect.",
            image_bytes=processed_bytes,
            generation_type=self.name,
            provider="local",
            model="pil",
            config={},
            source_asset_ids=[asset.id],
        )
```

2. Register it in `backend/app/services/generation/modules/__init__.py`:

```python
from app.services.generation.modules.myeffect import MyEffectModule

MODULE_CLASSES = [
    ...,
    MyEffectModule,
]
```

The effect will appear automatically in the Effects tab — no other changes needed.

---

## Data

All persistent data is stored in `./data/`:

| Path | Contents |
|---|---|
| `data/app.db` | SQLite database (settings, presets, schedules, history) |
| `data/results/` | Generated PNG files (deleted on reject, cleaned up after 7 days) |
| `data/generation-examples/` | Cached effect preview images |

---

## Scripts

- `scripts/measure_dailyfx_preset.py` reproduces the request-timing test against the local API.
  Example:
  ```bash
  python3 scripts/measure_dailyfx_preset.py --preset TestA --count 50
  ```
  It prints a markdown table with request time, asset name, date, and people, plus mean/min/max timing at the end.
- `scripts/render_filters_showcase.py` renders a showcase/contact sheet of all active filters and generation modules.

## Frontend Documentation

For a screen-by-screen overview of the UI, data flow, and browser state, see [docs/frontend.md](docs/frontend.md).

## Architecture

For the backend layering, generation pipeline, and history/review flow, see [docs/architecture.md](docs/architecture.md).

## Self-Hosting Guide

For a complete guide to running DailyFX on your own network, see [docs/self-hosting.md](docs/self-hosting.md).

## FAQ

### Do I need AI keys to use DailyFX?
No. AI keys are only needed for AI image effects. The rest of the app works with Immich alone.

### Where do generated images go?
They are stored in `data/results/` until you accept or reject them.

### Can I use DailyFX only inside my home network?
Yes. That is the intended use case for self-hosting.

### What should I back up?
Back up the `data/` directory, especially `data/app.db`.

---

## Architecture

```
backend/          FastAPI + SQLAlchemy + Alembic
  app/
    api/          Routes: settings, generation, health, push, debug, presets, schedules
    immich/       Immich API client
    notifications/ Web Push, ntfy, Gotify, Telegram, Home Assistant
      providers/  Split channel integrations (telegram, home_assistant, slack, discord, etc.)
    services/
      generation/
        engine.py         Compatibility entry points
        pipeline/         Decoupled staged pipeline package (planning, assets, execution, etc.)
        vision/           Modular AI vision provider adapters (gemini, openai, openrouter, etc.)
        config_validation.py API-boundary config schema validator
        persistence.py    Result persistence and history writes
        output.py         Notifications and webhooks
        modules/          Effect plugin system
      settings/           Settings response/connection helpers
      notifications/      Notification preset test helpers
    workers/
      scheduler.py        Automation loop
  healthcheck.py  Dedicated multi-check API & scheduler health status script

frontend/         React 19 + Vite + Tailwind CSS
  src/
    pages/        Modular route views:
      History/, Login.tsx, Presets/, Schedules/, Settings/
    api/          API client (typed)
    components/   RouteErrorBoundary.tsx (graceful route failure recovery)
    version.ts    Single source of truth version metadata
```

## License

Source-available for non-commercial use under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).

---

## Support

If you like this project and want to support its development, you can buy me a coffee:

* **Buy Me a Coffee:** [buymeacoffee.com/ferges](https://buymeacoffee.com/ferges)
* **Ko-fi:** [ko-fi.com/ferges](https://ko-fi.com/ferges)
