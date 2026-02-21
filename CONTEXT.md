# FIRE — Project Context & Handoff

## What Is This?

**Freedom Intelligent Routing Engine (FIRE)** — a hackathon project for Freedom Finance (Фридом Финанс).

An AI-powered pipeline that reads customer support tickets from CSV, classifies them with an LLM, geocodes client addresses, applies business routing rules, and assigns tickets to the right manager. Results are stored in PostgreSQL and displayed in a Next.js web dashboard with an AI assistant ("Star Task").

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python + FastAPI |
| LLM (text + vision) | `gpt-4.1-nano` via OpenAI API |
| Database | PostgreSQL |
| ORM | SQLAlchemy (sync) + psycopg2 |
| Geocoding | Hardcoded KZ city map + fuzzy matching (difflib) + Nominatim (OpenStreetMap) |
| Frontend | Next.js 14 (App Router) + Tailwind CSS + Recharts |

---

## Project Structure

```
freedom/
├── data/
│   ├── tickets.csv
│   ├── managers.csv
│   ├── business_units.csv
│   └── images/                 # Ticket screenshots (.png) for vision analysis
├── backend/
│   ├── .env                    # Secrets (not committed)
│   ├── .venv/                  # Python venv (not committed)
│   ├── requirements.txt
│   ├── database.py             # SQLAlchemy engine, init_db(), incremental migrations
│   ├── models.py               # ORM models (Ticket, TicketAnalysis, Manager, BusinessUnit, Assignment)
│   ├── schemas.py              # Pydantic response schemas
│   ├── llm.py                  # LLM: analyze_ticket(), analyze_image(), get_attachment_context()
│   ├── geocoding.py            # Multi-tier geocoding: hardcoded map → fuzzy → Nominatim
│   ├── routing.py              # Business rules engine + Round Robin state
│   ├── pipeline.py             # ETL: CSV → DB → LLM → route → save
│   └── main.py                 # FastAPI app + all endpoints
├── frontend/
│   ├── app/
│   │   ├── page.tsx            # Dashboard (KPIs + 4 charts + manager load table)
│   │   ├── tickets/page.tsx    # Filterable tickets table
│   │   ├── tickets/[id]/       # Ticket detail page
│   │   ├── managers/page.tsx   # Managers grouped by office
│   │   └── assistant/page.tsx  # AI assistant chat (Star Task)
│   └── components/
│       ├── Sidebar.tsx
│       ├── StatsCard.tsx
│       └── PipelineButton.tsx  # Run pipeline + Reset DB buttons
├── CLAUDE.md                   # Claude Code instructions (loaded automatically)
├── CONTEXT.md                  # This file
└── docker-compose.yml
```

---

## Environment Variables (`backend/.env`)

```
DATABASE_URL=postgresql://fire:fire123@localhost:5432/fire_db
LLM_API_KEY=<openai key>
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-nano
```

---

## Database Schema

```
tickets           — raw CSV data
  guid, gender, birth_date, description, attachment, segment
  country, region, city, street, house

ticket_analysis   — LLM analysis result (1:1 with ticket)
  ticket_type, sentiment, priority_score, language
  summary, recommendation
  client_lat, client_lon, nearest_office
  attachment_description    ← vision result OR missing-attachment warning

managers          — staff roster
  full_name, position, office, skills[], current_load

business_units    — offices with coordinates
  office_name, address, latitude, longitude

assignments       — routing result (1:1 with ticket)
  ticket_id, manager_id, assigned_office, round_robin_index
```

Incremental migrations run automatically on startup via `database._run_migrations()` using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/pipeline/run` | Trigger full pipeline (background task) |
| `GET` | `/api/pipeline/status` | Poll pipeline progress |
| `POST` | `/api/pipeline/reset` | Wipe all DB data, reset pipeline state |
| `GET` | `/api/tickets` | List tickets (filters: segment, language, ticket_type, office) |
| `GET` | `/api/tickets/{id}` | Single ticket detail |
| `GET` | `/api/managers` | List managers (filter: office) |
| `GET` | `/api/business-units` | List offices |
| `GET` | `/api/stats` | Aggregate stats for dashboard |
| `POST` | `/api/assistant` | AI assistant: natural language → SQL → chart data |

---

## Business Rules (routing.py)

Applied in strict cascade order:

### 1. Geography
- Kazakhstan client with known city → nearest office by Haversine distance
- **Single-office shortcut**: if city fuzzy-matches to a city with exactly one office and no street → assign immediately, skip distance calc
- **Equidistant tie-break**: if top-2 nearest offices are within 50 km → pick lower total manager load
- Foreign / unknown → 50/50 Round Robin between Астана and Алматы

### 2. Hard Skill Filters (all must pass)
- VIP or Priority segment → `VIP` skill required
- `Смена данных` → `Главный специалист` only
- KZ language → `KZ` skill; ENG language → `ENG` skill

### 3. Soft Senior Preference
- Негативный sentiment → prefer `Ведущий специалист` / `Главный специалист`
- Falls through to full eligible pool if no senior available

### 4. Round Robin
- Sort eligible by `current_load` ASC → top 2 → alternate via per-pool counter
- RR key = eligibility flags (`is_vip`, `is_data_change`, `language`, `needs_senior`)

### Fallback
No eligible at target office → try Астана → try Алматы.

---

## LLM: gpt-4.1-nano Notes

- Not a reasoning model — direct output, `max_tokens=512` sufficient
- Supports vision via `image_url` with inline base64 data URL
- `response_format={"type": "json_object"}` for structured output
- Follows instructions literally — prompts must be explicit

### Ticket Types

| Type | Definition |
|---|---|
| `Жалоба` | General complaint — dissatisfied, no compensation demand |
| `Претензия` | Formal claim explicitly demanding refund/compensation ("требую", "верните") |
| `Смена данных` | Change personal data (phone, passport, address, email) |
| `Консультация` | Question or information request |
| `Неработоспособность приложения` | App crash, login failure, technical error |
| `Мошеннические действия` | Fraud, unauthorized transaction, phishing |
| `Спам` | Ad/promotional content unrelated to client's account |

### Priority Scoring (1–10)

Base: Мошеннические действия=9, Претензия=8, Жалоба/Неработоспособность=6, Смена данных=5, Консультация=3, Спам=null.
Adjustments: +2 VIP/Priority (min 6), +1 Негативный, +1 legal threats / large sum.

---

## Geocoding (geocoding.py)

`geocode_client(city, region, country, street, house)` — multi-tier fallback:

1. Full street address → Nominatim (only if `street` provided)
2. Direct city lookup in `KZ_CITY_COORDS` (70+ cities hardcoded)
3. Direct region lookup
4. Fuzzy city match via `difflib` (catches 1-2 char typos)
5. Fuzzy region match
6. City-only Nominatim (unknown cities)
7. Partial substring match (legacy)

`CITY_TO_OFFICES` maps normalised city name → list of offices (ready for multi-branch cities).
Nominatim rate-limited to ≤1 req/sec automatically.

---

## Attachment Processing (llm.py)

`get_attachment_context(filename, description, data_dir)`:

| Case | Result |
|---|---|
| File in `data/images/` | `analyze_image()` → description injected into LLM prompt |
| Filename set, file missing | Warning in `attachment_description` |
| No file, description mentions "скрин"/etc. | Edge-case warning |
| Nothing | `None` |

`analyze_image(path)` → inline base64 `image_url` to gpt-4.1-nano.

Known attachment tickets:
- `a154a8e6` → `data_error.png`
- `b44f142b` → `order_error.png` (no text, image-only)
- `c577d3fd` → mentions attachment but file missing ⚠️
- `80c6ed25` → mentions screenshot but file missing ⚠️

---

## How to Run

```bash
# Start Postgres
brew services start postgresql@16

# Backend
cd ~/Documents/GitHub/freedom/backend && source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd ~/Documents/GitHub/freedom/frontend
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

# Pipeline
curl -X POST http://localhost:8000/api/pipeline/run
curl http://localhost:8000/api/pipeline/status
curl -X POST http://localhost:8000/api/pipeline/reset   # wipe + ready for fresh run
```

---

## Known Quirks

- `tickets.csv` columns have trailing spaces → stripped with `df.columns = [c.strip() ...]`
- Pipeline is idempotent — skips already-analyzed tickets; reset to rerun
- Round-robin counters are in-memory — reset on server restart
- Nominatim adds ~1.1s per street-address ticket to pipeline runtime
- `CITY_TO_OFFICES` keys are lowercase-normalised

---

## Status

### Done
- Full ETL pipeline: CSV → PostgreSQL → LLM → routing → assignments
- All 7 ticket types classified by gpt-4.1-nano
- All business routing rules implemented and validated
- Vision analysis via gpt-4.1-nano (same model, inline base64)
- Fuzzy address matching + street-level Nominatim geocoding
- Single-office shortcut + equidistant load tie-breaking
- Negative sentiment → senior manager soft preference
- Correct RR key (eligibility-based)
- Frontend: dashboard, tickets, ticket detail, managers, AI assistant
- DB reset endpoint + UI button

### Pending
- Docker Compose — written but untested (no Docker daemon)
- `frontend/.env.local` — `NEXT_PUBLIC_API_URL` passed manually
- Map view — Leaflet map for client → office assignments
