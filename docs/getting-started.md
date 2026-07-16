# Getting Started

This page is for people who want the shortest path to a working DailyFX setup.

## What DailyFX Does
DailyFX connects to your Immich library, generates styled versions of your photos, and lets you review the results before they are uploaded back to Immich.

For a short operator-friendly explanation of the workflow, see [How It Works](how-it-works.md).

## Before You Start
- You need a running Immich instance
- You need Docker and Docker Compose

## Quick Setup
1. Clone the repository.
2. Copy `.env.example` to `.env`.
3. Generate a strong, unique secret key and set it in `.env`:

```env
APP_SECRET_KEY=your-generated-secure-key
```

> [!IMPORTANT]
> The default placeholder value (`change-me-generate-a-long-random-secret`) from `.env.example` **must be replaced**. In production mode (`APP_ENV=production`), the application's preflight checks will fail and block the startup if this placeholder value is still used.

The example `.env` is already set up for the Docker stack, so `APP_ENV=production`, `DATA_DIR=/data`, and `DATABASE_URL=sqlite:////data/app.db` can stay as-is for a normal local run.

4. Start the app:

```bash
docker compose up --build -d
```

5. Open `http://localhost:8439` in your browser.

## First Things To Do
- Open **Settings** to enter your Immich connection details (URL & API Key) and test the connection.
- Open **People**, **Effects**, and **Notifications** tabs (under **Presets** on mobile) to configure your choices.
- Open **Schedules** if you want automatic generation.
- Open **History** to review and accept/reject generated images. Manual **Run now** requests appear there immediately as `Queued`, then switch to `Running` when the worker starts them.

## First Day Checklist
- Configure Immich in **Settings** and confirm the connection test succeeds.
- Create one people preset and one effect preset.
- Create one schedule and run it once with **Run now**.
- Open **History** and decide whether to accept or reject the result.
- If you use notifications, confirm the result arrives in the channel you expect.

## Notification Channels
DailyFX notification presets can target one or more comma-separated channels:
- Web Push
- ntfy
- Gotify
- Telegram Bot
- Home Assistant
- Slack
- Discord
- Apprise

## Optional AI Features
If you want AI-powered effects, enter your API keys for your preferred AI provider in the **Settings** tab. DailyFX supports:
- OpenAI (vision analysis + image generation)
- Gemini (vision analysis + image generation)
- OpenRouter (vision analysis + image generation)
- BytePlus (image generation only)
- Xiaomi (vision analysis + image generation)
For official key setup links, see [API documentation](api.md#ai-provider-key-setup).

For BytePlus AI Image, use the [BytePlus Model Management console](https://console.byteplus.com/ark/region:ark+ap-southeast-1/openManagement) to choose a ModelArk image model. Some models include a free tier or free trial quota, visible in the model details and pricing.

If you do not set them, the non-AI effects still work.

Per-schedule AI provider/model selection is configured in the **Schedules** tab.

## If You See a Login Screen
Enter the token from `APP_ACCESS_TOKEN` if your instance uses protected access.

## Common Problems
- No connection to Immich: check the URL and API key entered in the **Settings** tab.
- Login does not work: make sure the browser token matches `APP_ACCESS_TOKEN` in `.env`.
- No schedules run: check that the backend container is running.
- Images do not load: confirm the backend is reachable and the browser is allowed to access it.
- Files in `data/` owned by `root`: In [docker-compose.yml](../docker-compose.yml), the `api` service is configured with `user: "${UID:-1000}:${GID:-1000}"` to match your host user permissions. If your shell does not export `UID`/`GID` automatically, you can define them in your `.env` file (e.g. `UID=1000` and `GID=1000`) and rebuild the stack.


## Where To Read More
- [How It Works](how-it-works.md)
- [Self-hosting guide](self-hosting.md)
- [Frontend documentation](frontend.md)
- [API documentation](api.md)
