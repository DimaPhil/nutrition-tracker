# Nutrition Tracker

Telegram-first nutrition tracking with photo-based food detection and P/F/C macros.

This MVP processes photos only during active sessions and does **not** store images.

## Highlights

- Photo -> detected items -> portion workflow -> saved meal
- USDA FoodData Central (FDC) nutrition lookups with caching
- User food library with reuse + aliases
- History commands: `/today`, `/week`, `/month`, `/history`
- Admin endpoints (token-auth) for user/session/cost summaries

## System Overview

- **API**: FastAPI webhook (`/telegram/webhook`)
- **AI**: OpenAI Responses API (vision + Structured Outputs)
- **Storage**: Supabase Postgres
- **UI**: Telegram bot + inline keyboards

## Requirements

- Python 3.13
- Supabase project (Postgres)
- Telegram bot token
- OpenAI API key
- USDA FDC API key (data.gov)

## Environment Variables

Create a `.env` file in the repo root:

```
TELEGRAM_BOT_TOKEN=...
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
ADMIN_TOKEN=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.2
OPENAI_REASONING_EFFORT=high
OPENAI_STORE=false
FDC_API_KEY=...
FDC_BASE_URL=https://api.nal.usda.gov/fdc/v1
```

Notes:
- `OPENAI_STORE=false` for privacy.
- Photos are never stored. Telegram file IDs are removed after session completion.

## Local Setup

```
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run (Local)

```
uvicorn nutrition_tracker.api.asgi:app --reload
```

## Telegram Webhook

Configure Telegram to send updates to your server:

```
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<your-domain>/telegram/webhook
```

## Database

Supabase migration:

- `supabase/migrations/0001_mvp.sql`

Apply using your Supabase migration workflow.

## Tests

```
pytest
pytest --cov --cov-report=term-missing
```

## Quality Gates

```
pytest
ruff check src tests
ruff format --check src tests
```

## Admin Endpoints

All admin endpoints require the `X-Admin-Token` header.

- `GET /admin/health`
- `GET /admin/users`
- `GET /admin/users/{user_id}`
- `GET /admin/sessions`
- `GET /admin/costs`

## Security and Privacy

- Images are not stored (no Supabase Storage usage).
- Telegram file IDs are deleted after session completion.
- OpenAI Responses API uses `store=false`.

## Troubleshooting

- If you see 401 from `/admin/*`, verify `X-Admin-Token` matches `ADMIN_TOKEN`.
- If the bot is silent, confirm webhook is set and reachable.
- If vision fails, ensure `OPENAI_API_KEY` is valid and the model name is correct.
