# Nutrition Tracker (MVP)

Telegram-first nutrition tracking with photo-based food detection and P/F/C macros.

Photos are processed only during active sessions and are **never stored**.

## What this app does

1. A user sends a food photo to the Telegram bot.
2. The bot proposes detected items and guesses based on the user’s library.
3. The user confirms items, chooses products (library → USDA FDC), or enters manually.
4. The user confirms or enters grams.
5. The bot shows a macro summary and saves the meal.
6. The food is added to the user’s library for faster future matches.

## How it works (high level)

- **Vision**: The image is sent once to an OpenAI model with Structured Outputs to extract item candidates.
- **Selection**: For each item, the bot suggests:
  - the best match from the user’s library
  - fallback FDC results
  - manual entry (name + macros)
- **Portions**: Accept estimated grams or enter grams.
- **Summary**: Per-item macros and totals are shown before saving.
- **Storage**: Only meal logs and library entries are stored in Supabase Postgres. No images.

## Tech stack

- **Backend**: FastAPI
- **AI**: OpenAI Responses API (vision + Structured Outputs)
- **Nutrition DB**: USDA FoodData Central (FDC)
- **Storage**: Supabase Postgres
- **Frontend**: Telegram bot with inline keyboards

## Bot commands (MVP)

- `/start` — create user and set timezone
- `/today` — totals + meal list
- `/week` — daily totals + averages
- `/month` — daily totals + averages
- `/history` — last 10 meals (tap to view + edit grams)
- `/library` — top foods + add manual entry
- `/cancel` — cancel active session

## Setup (step by step)

### 1) Create a Telegram bot

- Talk to `@BotFather` → create a bot → copy the token.

### 2) Create a Supabase project

- Create a new project in Supabase.
- Copy:
  - **Project URL** → `SUPABASE_URL`
  - **Service Role Key** → `SUPABASE_SERVICE_KEY`

Apply the migration:

```
psql "<YOUR_SUPABASE_CONNECTION_STRING>" -f supabase/migrations/0001_mvp.sql
```

### 3) Get API keys

- OpenAI API key → `OPENAI_API_KEY`
- USDA FoodData Central key (data.gov) → `FDC_API_KEY`

### 4) Configure environments (local + production)

The app automatically loads `.env.<ENVIRONMENT>` first, then `.env`.

Create two files:

```
.env.local
.env.production
```

Example **.env.local**:

```
ENVIRONMENT=local
TELEGRAM_BOT_TOKEN=...
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_SERVICE_KEY=<local_service_role_key>
ADMIN_TOKEN=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.2
OPENAI_REASONING_EFFORT=high
OPENAI_STORE=false
FDC_API_KEY=...
FDC_BASE_URL=https://api.nal.usda.gov/fdc/v1
```

Example **.env.production**:

```
ENVIRONMENT=production
TELEGRAM_BOT_TOKEN=...
SUPABASE_URL=https://<your-prod-project>.supabase.co
SUPABASE_SERVICE_KEY=<prod_service_role_key>
ADMIN_TOKEN=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.2
OPENAI_REASONING_EFFORT=high
OPENAI_STORE=false
FDC_API_KEY=...
FDC_BASE_URL=https://api.nal.usda.gov/fdc/v1
```

To run in a specific environment:

```
ENVIRONMENT=local uvicorn nutrition_tracker.api.asgi:app --reload
```

or

```
ENVIRONMENT=production uvicorn nutrition_tracker.api.asgi:app
```

Notes:
- `OPENAI_STORE=false` ensures model responses are not stored by OpenAI.
- Photos are never stored in Supabase or on disk.

### 5) Install and run locally

```
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn nutrition_tracker.api.asgi:app --reload
```

Or use helper scripts:

```
bin/run_dev.sh
bin/run_prod.sh
bin/test.sh
bin/lint.sh
bin/format_check.sh
bin/supabase_start.sh
```

### 6) Set the Telegram webhook (local via ngrok)

Telegram requires a public HTTPS URL (no localhost).

1) Run the app:

```
bin/run_dev.sh
```

2) Start ngrok:

```
ngrok http 8000
```

3) Set the webhook using the HTTPS URL ngrok prints:

```
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<ngrok-id>.ngrok-free.app/telegram/webhook
```

4) Verify:

```
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo
```

### Production

```
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<your-domain>/telegram/webhook
```

## Deploy to Vercel (CD)

This repo is Vercel-ready with a serverless Python entrypoint.

### 1) Connect the repo

- Create a new Vercel project and import this repository.
- Vercel will detect `api/index.py` and use the Python runtime automatically.

### 2) Set environment variables

In Vercel → **Project Settings → Environment Variables**, set:

- `TELEGRAM_BOT_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `ADMIN_TOKEN`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_REASONING_EFFORT`
- `OPENAI_STORE`
- `FDC_API_KEY`
- `FDC_BASE_URL`

### 3) Deploy

Just push to `main`. Vercel builds and deploys automatically.

### 4) Set Telegram webhook to Vercel

```
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<your-vercel-domain>/telegram/webhook
```

### Notes

- Serverless entrypoint: `api/index.py`
- Vercel uses `requirements.txt` for dependencies.

## Admin UI

Open:

- `GET /admin/ui`

You’ll be prompted for your admin token. The UI calls:

- `GET /admin/users`
- `GET /admin/sessions`
- `GET /admin/costs`

## How meal logging looks in practice

1. User sends photo.
2. Bot: “I think I see: rice, chicken… Does this look right?”
3. User can “Looks right” or “Fix items”.
4. For each item, user picks:
   - library match
   - FDC option
   - manual entry
5. Bot asks for grams per item.
6. Bot shows macro summary and asks to save.

## Quality gates

```
pytest
pytest --cov --cov-report=term-missing
ruff check src tests
ruff format --check src tests
```

## Security & privacy

- Images are never stored.
- Telegram file IDs are removed after session completion.
- OpenAI responses use `store=false`.

## Troubleshooting

- **401 on /admin/**: check `X-Admin-Token` matches `ADMIN_TOKEN`.
- **Bot is silent**: webhook isn’t set or isn’t reachable.
- **Vision fails**: verify `OPENAI_API_KEY` and model name.
