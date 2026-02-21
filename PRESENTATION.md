---
marp: true
theme: default
paginate: true
style: |
  section {
    background: #0f172a;
    color: #e2e8f0;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    padding: 48px 60px;
  }
  h1 {
    color: #38bdf8;
    font-size: 2.2em;
    font-weight: 800;
    margin-bottom: 0.2em;
  }
  h2 {
    color: #7dd3fc;
    font-size: 1.4em;
    font-weight: 700;
    border-bottom: 2px solid #1e3a5f;
    padding-bottom: 8px;
    margin-bottom: 0.6em;
  }
  h3 {
    color: #93c5fd;
    font-size: 1.1em;
    margin-bottom: 0.3em;
  }
  p, li {
    color: #cbd5e1;
    font-size: 0.95em;
    line-height: 1.6;
  }
  strong {
    color: #f8fafc;
  }
  code {
    background: #1e293b;
    color: #67e8f9;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.88em;
  }
  pre {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 16px;
    font-size: 0.78em;
    color: #94a3b8;
  }
  pre code {
    background: none;
    padding: 0;
    color: inherit;
  }
  .pill {
    display: inline-block;
    background: #1e3a5f;
    color: #7dd3fc;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.82em;
    margin: 2px;
  }
  table {
    border-collapse: collapse;
    width: 100%;
    font-size: 0.88em;
  }
  th {
    background: #1e3a5f;
    color: #7dd3fc;
    padding: 8px 12px;
    text-align: left;
  }
  td {
    padding: 7px 12px;
    border-bottom: 1px solid #1e293b;
    color: #cbd5e1;
  }
  tr:nth-child(even) td { background: #0f1e33; }
  section.title {
    display: flex;
    flex-direction: column;
    justify-content: center;
    background: linear-gradient(135deg, #0f172a 0%, #0c2340 100%);
  }
  section.title h1 { font-size: 3em; }
  section.title .subtitle { color: #64748b; font-size: 1.1em; margin-top: 0.5em; }
  section.title .tagline { color: #38bdf8; font-size: 1.3em; margin-top: 1.5em; font-weight: 600; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  .card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 16px 20px;
  }
  .highlight { color: #38bdf8; font-weight: 700; }
  .badge-green { color: #4ade80; }
  .badge-yellow { color: #fbbf24; }
  .badge-red { color: #f87171; }
---

<!-- _class: title -->

# F.I.R.E.
## Freedom Intelligent Routing Engine

<div class="subtitle">Hackathon Project — Freedom Finance (Фридом Финанс)</div>
<div class="tagline">AI-powered customer support routing at scale</div>

---

## The Problem

Freedom Finance processes thousands of customer support tickets every day.

**Without automation:**
- Tickets are manually read and assigned → slow, inconsistent
- Wrong manager gets the ticket (wrong office, missing skills, overloaded)
- VIP clients handled by random staff — not qualified specialists
- No visibility: which office is overwhelmed? which type dominates?

**The ask:**
> Build a system that reads raw ticket text, understands the issue, finds the right manager, and gives ops teams a live dashboard.

---

## What FIRE Does — End to End

```
CSV Files                    Intelligence Layer              Output
─────────                    ──────────────────              ──────
tickets.csv      ──►  LLM Classification  ──►  Ticket Type   ──►  Database
managers.csv     ──►  Vision Analysis     ──►  Language           │
business_units.csv   Geocoding            ──►  Priority      ──►  Dashboard
                     Routing Rules        ──►  Manager Assigned    │
                                               Office             API
```

**One button → full pipeline runs in seconds**

1. Load CSVs into PostgreSQL
2. Classify every ticket with `gpt-5-nano` (+ vision for images)
3. Geocode client addresses (7-tier fallback strategy)
4. Apply business routing rules + Round Robin balancer
5. Save results → serve live dashboard

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| **Backend** | Python + FastAPI | Async, fast, zero boilerplate |
| **LLM** | `gpt-5-nano` (OpenAI) | Vision + text, cheap, fast, literal |
| **Database** | PostgreSQL + SQLAlchemy | Relational, reliable, flexible |
| **Geocoding** | 2GIS API (`ru_KZ`) + difflib | CIS-optimised, KZ bbox validation, typo-tolerant |
| **Frontend** | Next.js 14 + Tailwind | App Router, dark UI, Recharts |
| **AI Assistant** | `gpt-5-nano` → SQL | NL → SQL → live chart |

**Key principle:** one model for everything — text classification, image analysis, and the AI chat assistant. No extra services, no complexity.

---

## LLM Classification — gpt-5-nano

**Why gpt-5-nano?**
- Fastest GPT-4-class model — ~200ms per ticket
- Follows instructions **literally** → structured JSON output, zero post-processing
- Native vision — same model reads screenshots
- 1M token context window for future bulk analysis

**7 Ticket Types classified:**

| Type | Trigger |
|---|---|
| Жалоба | General dissatisfaction |
| Претензия | Explicit demand: "требую", "верните деньги" |
| Смена данных | Update phone, passport, email, address |
| Консультация | Question / information request |
| Неработоспособность приложения | App crash, login failure |
| Мошеннические действия | Fraud, phishing, unauthorized transaction |
| Спам | Promotional content — no routing needed |

---

## LLM Prompt Engineering

**What works for gpt-5-nano:**

1. **Explicit schema** — output format defined at the end (sandwich pattern)
2. **Literal definitions** — "Претензия" = when the word "требую" appears; no ambiguity
3. **Compact system prompt** — model follows short, direct instructions better

```
## OUTPUT FORMAT
Output this exact JSON and nothing else:
{
  "ticket_type": "...",
  "sentiment": "Позитивный|Нейтральный|Негативный",
  "priority": <1–10 or null for Спам>,
  "language": "RU|KZ|ENG",
  "summary": "...",
  "recommendation": "..."
}
```

**Fallback chain:** heuristic rules (fraud/spam keywords) → LLM → static defaults

---

## Vision Analysis

**Same model, same API call — zero extra services**

When a ticket has an image attachment (`data/images/*.png`):

```python
response = client.chat.completions.create(
    model="gpt-5-nano",
    messages=[{"role": "user", "content": [
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{img_data}"}},
        {"type": "text", "text": "Describe what error/screen this shows in Russian..."},
    ]}]
)
```

**Result:** attachment description injected into the ticket classification prompt → LLM sees both text and image context when deciding type/priority.

**No Ollama. No Anthropic API. Just OpenAI.**

---

## Geocoding — 5-Tier Fallback

Client addresses in the CSV often have **typos, missing fields, or Latin-script city names.**

```
Input: city="Красный Яр", region="Акмолинская"
                          ↓
1. 2GIS API — "Красный Яр, Акмолинская, Казахстан"  → (53.32, 69.26) ✓
   locale=ru_KZ  +  KZ bbox check  ← rejects out-of-KZ hits
2. 2GIS API — "region, Казахстан"  (if no city or city failed)
3. Direct region lookup in KZ_CITY_COORDS (offline fallback)
4. Fuzzy region match (difflib, cutoff=0.75)
5. Partial substring fallback
```

**Latin aliases handled:** "Aktau" → "Актау", "Semipalatinsk" → "Семей", etc.
`locale=ru_KZ` pins results to Kazakhstan; bbox double-checks coordinates are within ~40.5–55.5°N, 50.2–87.4°E.

---

## Business Routing Rules — Cascade Order

Applied strictly in sequence for every non-spam ticket:

### 1. Geography → Target Office
- KZ client + known city → **Haversine nearest office**
- City maps to **single office** and no street → instant shortcut (no calculation)
- Top-2 offices within **50 km** → tie-break by **lower total manager load**
- Foreign / unknown country → **50/50 Round Robin** Астана ↔ Алматы

### 2. Hard Skill Filters
- `VIP` or `Priority` segment → manager must have **VIP skill**
- `Смена данных` ticket → **Главный специалист** only
- Language `KZ` → **KZ skill**; `ENG` → **ENG skill**

### 3. Soft Senior Preference
- `Негативный` sentiment → prefer **Ведущий / Главный специалист**

### 4. Round Robin → top-2 eligible by load → alternate

---

## Round Robin — The Right Way

**The problem with naive RR:**
Using raw ticket fields (`segment + type + language`) as the key creates too many counters — each combination gets its own, so the alternation never happens within the actual manager pool.

**Our fix: eligibility-flag key**

```python
def build_rr_key(office, is_vip, is_data_change, language, needs_senior):
    lang = language if language in ("KZ", "ENG") else "RU"
    return f"{office}|vip={is_vip}|data={is_data_change}|lang={lang}|senior={needs_senior}"
```

All tickets competing for the **same pool of managers** share one counter → true alternation across the entire workday.

---

## Fallback Chains — Nothing Gets Dropped

Every ticket is guaranteed an outcome:

```
Target office → filter managers → eligible?
                                      │
                              No ─────┤
                                      ├─► Try Астана
                                      │       ↓ still no?
                                      └─► Try Алматы
                                              ↓ still no?
                                          Analysis saved, manager = NONE
                                          (ticket logged, ops team alerted)
```

Spam tickets: **classified and logged, never assigned** — they inflate no one's load.

---

## Frontend — Live Dashboard

**5 pages, all data-driven:**

| Page | What it shows |
|---|---|
| **Dashboard** | KPI cards + 4 charts (type/sentiment/office/segment) + manager load table |
| **Tickets** | Filterable full table (type, language, segment, office) |
| **Ticket Detail** | Full analysis: type, sentiment, priority, summary, recommendation, image desc. |
| **Managers** | Roster grouped by office, skills badges, current load |
| **AI Assistant** | Natural language → SQL → bar/pie/line chart |

**Tech:** Next.js 14 App Router · Tailwind CSS · Recharts · Lucide icons

---

## AI Assistant — "Star Task"

**How it works:**

```
User: "Покажи топ-5 менеджеров по нагрузке"
              ↓
  gpt-5-nano receives:
    - System: schema of all 5 tables
    - User: the question + DB summary
              ↓
  Returns JSON:
  {
    "answer": "Топ-5 самых загруженных менеджеров:",
    "sql": "SELECT full_name AS label, current_load AS value
            FROM managers ORDER BY current_load DESC LIMIT 5",
    "chart_type": "bar",
    "chart_title": "Нагрузка менеджеров"
  }
              ↓
  Backend runs SQL → returns data → frontend renders chart
```

**Any business question → instant visualization.**

---

## Key Design Decisions

### Why one model for everything?
gpt-5-nano handles text + images + SQL generation. No model routing, no fallback services, no additional API keys.

### Why heuristic pre-classification?
Fast-path rules (keyword matching for fraud, spam, claims) run in microseconds. Only ambiguous tickets hit the LLM → 30–50% fewer API calls.

### Why 2GIS instead of Google Maps?
2GIS is purpose-built for CIS/Central Asia — superior Kazakhstan address data. `locale=ru_KZ` keeps results within KZ; a bounding box check rejects any stray out-of-country hits. difflib fuzzy matching handles typos offline. Latin-script city names (e.g. "Aktau") normalised automatically via alias table.

### Why eligibility-flag RR keys?
Ensures fair alternation within each logical manager pool, not just within each unique ticket-field combination. Matches real-world call center behavior.

---

## Results

| Metric | Value |
|---|---|
| Tickets processed | All CSV rows, idempotent re-runs |
| Classification accuracy | Validated against labeled ground-truth CSV |
| Avg LLM latency | ~200–400 ms per ticket |
| Geocoding success rate | ~95%+ (7-tier fallback) |
| Offices covered | 15 across Kazakhstan |
| Manager skill matching | VIP, KZ, ENG, Главный специалист |
| Frontend pages | 5 (dashboard, tickets, detail, managers, assistant) |

**Pipeline is idempotent** — re-run any time, already-analyzed tickets are skipped.
**Reset button** — wipe DB and start fresh in one click.

---

<!-- _class: title -->

# Live Demo

## dashboard → tickets → ticket detail → managers → AI assistant

<div class="subtitle">Running on localhost:3000 + localhost:8000</div>

---

## What's Next

- **Map view** — Leaflet map showing client → office assignments geographically
- **Docker Compose** — one-command deployment (written, needs testing)
- **Accuracy dashboard** — live model accuracy metrics in the UI
- **Batch re-classification** — re-run LLM on a subset without full reset
- **Webhook / real-time** — push new tickets from CRM without CSV import

---

<!-- _class: title -->

# Thank You

**F.I.R.E. — Freedom Intelligent Routing Engine**

`FastAPI` · `gpt-5-nano` · `PostgreSQL` · `Next.js 14`

<div class="subtitle">Built for Freedom Finance Hackathon · 2025</div>
