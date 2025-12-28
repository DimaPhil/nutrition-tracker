`# MVP Checklist

Tracking items for the Telegram photo → calories + PFC MVP. Checkboxes will be updated as items are completed.

## Epic 0 — Project skeleton
- [x] FastAPI app scaffold + webhook endpoint
- [x] Supabase schema migrations
- [x] Admin auth scaffold (server-side)
- [x] `/start` creates user + settings row

## Epic 1 — Session state machine
- [x] `photo_sessions` lifecycle
- [x] Callback routing (inline keyboard actions)
- [x] Session resume logic
- [x] Photo triggers session + at least one question loop works

## Epic 2 — Telegram photo → OpenAI vision extract
- [x] Telegram `getFile` download
- [x] Base64 data URL for OpenAI image input
- [x] Structured Outputs schema for vision extraction
- [x] `store: false` for OpenAI responses
- [x] Bot replies with detected items + confidence

## Epic 3 — USDA FDC integration
- [x] Food search endpoint
- [x] Food details endpoint
- [x] Caching (query + fdc_id)
- [x] Nutrient mapping to calories/P/F/C
- [x] Given “Kirkland chicken breast” returns macros

## Epic 4 — User library
- [x] CRUD + alias support
- [x] Ranking: recent + frequent foods
- [x] On save: update use_count + last_used_at
- [x] Repeated food becomes top suggestion after 1–2 uses

## Epic 5 — Portion workflow
- [x] Grams entry parser
- [x] Estimate acceptance flow
- [x] Recompute + summary
- [x] User can log 2 items with weights and save

## Epic 6 — History & stats commands
- [x] `/today` totals + list
- [x] `/week` daily totals + avg
- [x] `/month` daily totals + avg
- [x] `/history` last N logs
- [x] Aggregation respects timezone

## Epic 7 — Admin MVP
- [x] Users list + brief stats
- [x] User detail (meal logs + library + corrections)
- [x] Sessions list with context_json
- [x] Cost metrics per day/model
- [x] Debug: can see why bot asked a question and what got saved
