# Fantasy Football Manager v10

Python + FastAPI backend with React frontend. Deploys to Railway in minutes.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload --port 8000

# Open in browser
open http://localhost:8000
```

## Deploy to Railway

1. Create a free account at [railway.app](https://railway.app)
2. Install the Railway CLI: `npm install -g @railway/cli`
3. From this folder:
```bash
railway login
railway init
railway up
```
4. Your app is live at the URL Railway assigns (shown after deploy)

No environment variables required for basic use. The app works entirely with Sleeper's public API.

## Project Structure

```
v10/
├── main.py                  # FastAPI entry point
├── requirements.txt         # Python dependencies
├── railway.toml             # Railway deploy config
├── routers/
│   └── analysis.py          # All feature endpoints
├── services/
│   ├── cache.py             # TTL caching layer
│   └── sleeper_client.py    # Sleeper API client
└── frontend/
    └── index.html           # React SPA
```

## Features

All features from v9 are ported:

**Alerts**: OUT/IR Starters, Questionable Starters, Starters on Bye, Open Spots

**Analysis**: Week Analysis, Week Record, There's A Chance, Optimal Lineup,
Upgrade Recommendations, My Position Needs, Overview (Contender + Strategy)

**Predictions**: Season Forecast

**Draft Data**: All Draft Picks, Draft Dates, Live Draft Tracker

## API Endpoints

All endpoints accept POST with `{"username": "...", "week": 2}`:

- `POST /api/alerts/injured-starters`
- `POST /api/alerts/questionable-starters`
- `POST /api/alerts/starters-on-bye`
- `POST /api/alerts/open-starter-spots`
- `POST /api/analysis/week`
- `POST /api/analysis/week-record`
- `POST /api/analysis/theres-a-chance`
- `POST /api/analysis/optimal-lineup`
- `POST /api/analysis/upgrade-recommendations`
- `POST /api/analysis/position-needs`
- `POST /api/analysis/overview`
- `POST /api/analysis/season-forecast`
- `POST /api/analysis/draft-picks`
- `POST /api/analysis/draft-dates`
- `POST /api/analysis/live-draft`

## Key Improvements Over v9

- **Server-side caching**: Rosters, users, players DB cached per session — no duplicate API calls
- **Parallel fetching**: Uses `asyncio.gather` to fetch multiple endpoints simultaneously
- **Proper architecture**: Backend handles all API calls, frontend is pure UI
- **No CORS issues**: Backend proxies all Sleeper API calls
- **Mobile-first UI**: Clean React interface that works on iPhone/iPad
- **Anthropic API ready**: Backend can call Claude directly without CORS restriction
