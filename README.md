# F.I.R.E. — Freedom Intelligent Routing Engine

AI-powered ticket routing system for Freedom Finance customer support.

## Quick Start

### 1. Set API key
```bash
echo "ANTHROPIC_API_KEY=your_key_here" > .env
```

### 2. Start with Docker Compose
```bash
docker compose --env-file .env up --build
```

- Backend API: http://localhost:8000
- Frontend UI: http://localhost:3000
- API Docs: http://localhost:8000/docs

### 3. Run pipeline
Open http://localhost:3000 and click **"Запустить пайплайн"**.

Place ticket screenshots referenced in CSV (`Вложения`) under `data/images/` (e.g. `data/images/order_error.png`).

This will:
1. Load all CSV data into PostgreSQL
2. Run Claude AI analysis on each ticket (type, sentiment, priority, language, summary)
3. Geocode client addresses
4. Apply business routing rules
5. Assign tickets to managers via Round Robin

---

## Local Development (without Docker)

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # fill in your keys

# Start PostgreSQL (e.g., via Docker)
docker run -d -e POSTGRES_USER=fire -e POSTGRES_PASSWORD=fire123 -e POSTGRES_DB=fire_db -p 5432:5432 postgres:16-alpine

uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

---

## Architecture

```
tickets.csv ──┐
managers.csv ─┼──► PostgreSQL ──► FastAPI ──► Next.js UI
business.csv ─┘         ↑
                    Claude API
                  (LLM Analysis)
```

### Business Rules

1. **Geo Filter**: Nearest office by Haversine distance. Foreign/unknown → 50/50 Astana/Almaty.
2. **Skill Filter**:
   - VIP/Priority segment → manager must have `VIP` skill
   - Ticket type "Смена данных" → must be `Главный специалист`
   - Language KZ → manager must have `KZ` skill
   - Language ENG → manager must have `ENG` skill
3. **Round Robin**: Top-2 eligible managers by current load, alternating assignment.

### Stack
- **Backend**: Python + FastAPI + SQLAlchemy + psycopg2
- **AI**: Claude claude-sonnet-4-6 (Anthropic SDK) with tool_use for structured JSON
- **Geocoding**: Hardcoded Kazakhstan city coordinates + Haversine distance
- **Database**: PostgreSQL
- **Frontend**: Next.js 14 + Tailwind CSS + Recharts
- **Star Task**: AI assistant with natural language → SQL → chart generation
