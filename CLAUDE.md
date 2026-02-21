# FIRE — Claude Code Project Guide

## What Is This

**Freedom Intelligent Routing Engine (FIRE)** — hackathon project for Freedom Finance (Фридом Финанс).
AI pipeline: CSV tickets → LLM classification → geocoding → business-rule routing → manager assignment.
Results stored in PostgreSQL, displayed in a Next.js dashboard.

---

## How to Run

```bash
# 1. Start Postgres (if not already running)
brew services start postgresql@16

# 2. Backend (Tab 1)
cd ~/Documents/GitHub/freedom/backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 3. Frontend (Tab 2)
cd ~/Documents/GitHub/freedom/frontend
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

# 4. Trigger pipeline (any terminal)
curl -X POST http://localhost:8000/api/pipeline/run
curl http://localhost:8000/api/pipeline/status

# 5. Reset DB (wipes all data, ready for fresh run)
curl -X POST http://localhost:8000/api/pipeline/reset
# OR via the "Сбросить БД" button in the dashboard UI
```

---

## Key Files

| File | Purpose |
|---|---|
| `backend/llm.py` | LLM calls: `analyze_ticket()`, `analyze_image()`, `get_attachment_context()` |
| `backend/geocoding.py` | City coords map, fuzzy matching, Nominatim, `find_sorted_offices()` |
| `backend/routing.py` | Business rules engine + Round Robin state |
| `backend/pipeline.py` | ETL: CSV → DB → LLM → route → save |
| `backend/main.py` | FastAPI app + all endpoints |
| `backend/models.py` | SQLAlchemy ORM models |
| `backend/database.py` | Engine, `init_db()`, incremental migrations |
| `data/` | Input CSVs + `images/` subfolder for ticket screenshots |

---

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy (sync) + psycopg2
- **LLM**: `gpt-4.1-nano` via OpenAI API (text classification **and** vision)
- **DB**: PostgreSQL — user=fire, password=fire123, db=fire_db
- **Geocoding**: Hardcoded KZ city map → fuzzy matching (difflib) → Nominatim (OSM)
- **Frontend**: Next.js 14 App Router + Tailwind + Recharts
- **venv**: `backend/.venv/` — always activate before running backend

---

## LLM: gpt-4.1-nano Critical Notes

- **NOT a reasoning model** — no internal chain-of-thought, direct output
- `max_tokens=512` is sufficient for ticket JSON
- **Supports vision** via `image_url` with inline base64 — same client for text + images
- Use `response_format={"type": "json_object"}` for structured output
- Follows instructions **literally** — prompts must be explicit, no implicit assumptions
- System prompt style: Role → Rules per field → Output schema (schema also at end)

---

## Image Attachments

- Place images in `data/images/` (the `ATTACHMENTS_SUBDIR`)
- `analyze_image(path)` sends as `data:image/png;base64,...` via `image_url` content block
- `get_attachment_context()` handles 4 cases: file found → analyze; file missing → warning; description references attachment but no file → edge-case warning; nothing → `None`
- Tickets with known attachments: `a154a8e6` (data_error.png), `b44f142b` (order_error.png)

---

## Geocoding Strategy (geocoding.py)

Multi-tier fallback in `geocode_client()`:
1. Full street address via Nominatim (if `street` is provided)
2. Direct city lookup in `KZ_CITY_COORDS` hardcoded map
3. Direct region lookup
4. Fuzzy city lookup via `difflib` (catches 1-2 char typos)
5. Fuzzy region lookup
6. City-only Nominatim (unknown cities)
7. Partial substring match (legacy)

`CITY_TO_OFFICES` maps city → list of offices. If a city has exactly one office and no street address is given, routing short-circuits to that office without a distance calculation.

---

## Business Rules (routing.py)

Strict cascade order:

1. **Geo**: nearest office by Haversine; foreign/unknown → 50/50 Астана/Алматы
2. **Single-office shortcut**: if city fuzzy-matches to exactly one office → assign immediately
3. **Equidistant tie-break**: if top-2 offices are within 50km → pick lower manager load
4. **Hard skill filters** (all must pass):
   - VIP/Priority segment → manager must have `VIP` skill
   - `Смена данных` → must be `Главный специалист`
   - KZ language → `KZ` skill; ENG language → `ENG` skill
5. **Soft senior preference**: `Негативный` sentiment → prefer `Ведущий/Главный специалист`
6. **Round Robin**: sort eligible by `current_load` ASC → top 2 → alternate by RR counter
7. **RR key** uses eligibility flags (`is_vip`, `is_data_change`, `language`, `needs_senior`), not raw ticket values

Fallback: if no eligible manager at nearest office → try Астана → Алматы.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/pipeline/run` | Start pipeline (background task) |
| `GET` | `/api/pipeline/status` | Poll progress |
| `POST` | `/api/pipeline/reset` | Wipe all DB data (safe reset) |
| `GET` | `/api/tickets` | List tickets (filters: segment, language, ticket_type, office) |
| `GET` | `/api/tickets/{id}` | Ticket detail |
| `GET` | `/api/managers` | Managers (filter: office) |
| `GET` | `/api/stats` | Aggregate stats for dashboard |
| `POST` | `/api/assistant` | AI assistant: NL query → SQL → chart data |

---

## DB Schema

```
tickets           — raw CSV data (guid, description, attachment, segment, country, region, city, street, house)
ticket_analysis   — LLM output (ticket_type, sentiment, priority_score, language, summary, recommendation,
                    client_lat, client_lon, nearest_office, attachment_description)
managers          — staff (full_name, position, office, skills[], current_load)
business_units    — offices (office_name, address, latitude, longitude)
assignments       — routing result (ticket → manager, assigned_office, round_robin_index)
```

Incremental migrations run on startup via `database._run_migrations()` using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.

---

## Known Quirks

- `tickets.csv` columns have trailing spaces — stripped with `df.columns = [c.strip() for c in df.columns]`
- Pipeline is idempotent — skips already-analyzed tickets; use reset to rerun from scratch
- Round-robin counters are in-memory — reset on server restart (fine for hackathon)
- Nominatim rate limit: 1 req/sec — pipeline adds 1.1s sleep between calls automatically
- `CITY_TO_OFFICES` keys are lowercase-normalised office names (e.g. `"алматы"` → `["Алматы"]`)
