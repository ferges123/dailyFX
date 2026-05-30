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
3. Fill in the required secret key in `.env`:

```env
APP_SECRET_KEY=generate-a-long-random-secret
```

The example `.env` is already set up for the Docker stack, so `APP_ENV=production`, `DATA_DIR=/data`, and `DATABASE_URL=sqlite:////data/app.db` can stay as-is for a normal local run.

4. Start the app:

```bash
docker compose up --build -d
```

5. Open `http://localhost:8439` in your browser.

## First Things To Do
- Open **Settings** to enter your Immich connection details (URL & API Key) and test the connection.
- Open **Filters**, **Effects**, and **Notifications** tabs (under **Presets** on mobile) to configure your choices.
- Open **Schedules** if you want automatic generation.
- Open **History** to review and accept/reject generated images.

## First Day Checklist
- Configure Immich in **Settings** and confirm the connection test succeeds.
- Create one filter preset and one effect preset.
- Create one schedule and run it once with **Run now**.
- Open **History** and decide whether to accept or reject the result.
- If you use notifications, confirm the result arrives in the channel you expect.

## Optional AI Features
If you want AI-powered effects, enter your API keys for your preferred AI provider in the **Settings** tab. DailyFX supports:
- OpenAI
- Gemini
- OpenRouter
- BytePlus
- Xiaomi

If you do not set them, the non-AI effects still work.

Per-schedule AI provider/model selection is configured in the **Schedules** tab.

## If You See a Login Screen
Enter the token from `APP_ACCESS_TOKEN` if your instance uses protected access.

## Common Problems
- No connection to Immich: check the URL and API key entered in the **Settings** tab.
- Login does not work: make sure the browser token matches `APP_ACCESS_TOKEN` in `.env`.
- No schedules run: check that the scheduler container is running.
- Images do not load: confirm the backend is reachable and the browser is allowed to access it.

## Where To Read More
- [How It Works](how-it-works.md)
- [Self-hosting guide](self-hosting.md)
- [Frontend documentation](frontend.md)
- [API documentation](api.md)
