import httpx
import asyncio
from services.cache import *

BASE_URL = "https://api.sleeper.app/v1"
PROJ_URL = "https://api.sleeper.app/projections/nfl"
STATS_URL = "https://api.sleeper.app/stats/nfl"

async def _get(url: str) -> dict | list:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()

# ── USER ──────────────────────────────────────────────────────────────────────

async def get_user(username: str) -> dict:
    return await _get(f"{BASE_URL}/user/{username}")

# ── NFL STATE ─────────────────────────────────────────────────────────────────

async def get_nfl_state() -> dict:
    cached = get_cached(nfl_state_cache, "state")
    if cached is not None:
        return cached
    data = await _get(f"{BASE_URL}/state/nfl")
    return set_cached(nfl_state_cache, "state", data)

# ── PLAYERS ───────────────────────────────────────────────────────────────────

async def get_players() -> dict:
    cached = get_cached(players_cache, "players")
    if cached is not None:
        return cached
    data = await _get(f"{BASE_URL}/players/nfl")
    return set_cached(players_cache, "players", data)

# ── LEAGUES ───────────────────────────────────────────────────────────────────

async def get_leagues(user_id: str, season: str) -> list:
    key = f"{user_id}/{season}"
    cached = get_cached(leagues_cache, key)
    if cached is not None:
        return cached
    try:
        data = await _get(f"{BASE_URL}/user/{user_id}/leagues/nfl/{season}")
    except Exception:
        data = []
    return set_cached(leagues_cache, key, data if isinstance(data, list) else [])

# ── ROSTERS ───────────────────────────────────────────────────────────────────

async def get_rosters(league_id: str) -> list:
    cached = get_cached(rosters_cache, league_id)
    if cached is not None:
        return cached
    try:
        data = await _get(f"{BASE_URL}/league/{league_id}/rosters")
    except Exception:
        data = []
    result = data if isinstance(data, list) else []
    # Ensure every roster has a players list
    for r in result:
        if r.get("players") is None:
            r["players"] = []
    return set_cached(rosters_cache, league_id, result)

# ── LEAGUE USERS ──────────────────────────────────────────────────────────────

async def get_league_users(league_id: str) -> list:
    cached = get_cached(league_users_cache, league_id)
    if cached is not None:
        return cached
    try:
        data = await _get(f"{BASE_URL}/league/{league_id}/users")
    except Exception:
        data = []
    result = data if isinstance(data, list) else []
    return set_cached(league_users_cache, league_id, result)

# ── MATCHUPS ──────────────────────────────────────────────────────────────────

async def get_matchups(league_id: str, week: int) -> list:
    key = f"{league_id}/{week}"
    cached = get_cached(matchups_cache, key)
    if cached is not None:
        return cached
    data = await _get(f"{BASE_URL}/league/{league_id}/matchups/{week}")
    return set_cached(matchups_cache, key, data or [])

# ── TRADED PICKS ──────────────────────────────────────────────────────────────

async def get_traded_picks(league_id: str) -> list:
    try:
        return await _get(f"{BASE_URL}/league/{league_id}/traded_picks")
    except Exception:
        return []

# ── DRAFTS ────────────────────────────────────────────────────────────────────

async def get_drafts(league_id: str) -> list:
    try:
        return await _get(f"{BASE_URL}/league/{league_id}/drafts")
    except Exception:
        return []

async def get_draft(draft_id: str) -> dict:
    return await _get(f"{BASE_URL}/draft/{draft_id}")

async def get_draft_picks(draft_id: str) -> list:
    try:
        return await _get(f"{BASE_URL}/draft/{draft_id}/picks")
    except Exception:
        return []

async def get_draft_traded_picks(draft_id: str) -> list:
    try:
        return await _get(f"{BASE_URL}/draft/{draft_id}/traded_picks")
    except Exception:
        return []

# ── PROJECTIONS ───────────────────────────────────────────────────────────────

async def get_projections(season: str, week: int) -> list:
    key = f"{season}/{week}"
    cached = get_cached(projections_cache, key)
    if cached is not None:
        return cached
    try:
        data = await _get(
            f"{PROJ_URL}/{season}/{week}?season_type=regular"
            "&position[]=QB&position[]=RB&position[]=WR&position[]=TE&position[]=K&position[]=DEF"
        )
        return set_cached(projections_cache, key, data or [])
    except Exception:
        return []

# ── STATS ─────────────────────────────────────────────────────────────────────

async def get_stats(season: str, week: int) -> list:
    key = f"{season}/{week}"
    cached = get_cached(stats_cache, key)
    if cached is not None:
        return cached
    try:
        data = await _get(f"{STATS_URL}/{season}/{week}?season_type=regular")
        return set_cached(stats_cache, key, data or [])
    except Exception:
        return []

# ── TRENDING ──────────────────────────────────────────────────────────────────

async def get_trending(kind: str = "add", hours: int = 24, limit: int = 50) -> list:
    """Sleeper's public trending list: [{player_id, count}]. kind = 'add' | 'drop'."""
    key = f"{kind}/{hours}/{limit}"
    cached = get_cached(trending_cache, key)
    if cached is not None:
        return cached
    try:
        data = await _get(f"{BASE_URL}/players/nfl/trending/{kind}?lookback_hours={hours}&limit={limit}")
    except Exception:
        data = []
    return set_cached(trending_cache, key, data if isinstance(data, list) else [])

# ── TRANSACTIONS ──────────────────────────────────────────────────────────────

async def get_transactions(league_id: str, week: int) -> list:
    try:
        return await _get(f"{BASE_URL}/league/{league_id}/transactions/{week}")
    except Exception:
        return []

# ── HELPERS ───────────────────────────────────────────────────────────────────

def build_proj_map(proj_array: list, scoring_settings: dict) -> dict:
    """Build player_id → projected pts map for a specific league's scoring."""
    proj_map = {}
    for entry in proj_array:
        pid = entry.get("player_id")
        if not pid:
            continue
        stats = entry.get("stats") or {}
        pts = 0.0
        for stat, val in stats.items():
            if stat in scoring_settings:
                pts += scoring_settings[stat] * val
        if pts == 0:
            rec = scoring_settings.get("rec", 0)
            if rec >= 1:
                pts = stats.get("pts_ppr", 0)
            elif rec >= 0.5:
                pts = stats.get("pts_half_ppr", 0)
            else:
                pts = stats.get("pts_std", 0)
        proj_map[str(pid)] = round(pts, 2)
    return proj_map

def build_stats_map(stats_array: list) -> dict:
    """Build player_id → stats dict from the week stats array."""
    stats_map = {}
    for entry in stats_array:
        pid = entry.get("player_id")
        if pid:
            stats_map[str(pid)] = entry.get("stats") or {}
    return stats_map

async def get_user_context(username: str) -> tuple[dict, dict, str, int, list, dict]:
    """
    Fetch all common context in parallel:
    Returns: (user, nfl_state, season, current_week, leagues, players_db)
    """
    user, nfl_state = await asyncio.gather(
        get_user(username),
        get_nfl_state()
    )
    season = nfl_state.get("season", "2025")
    current_week = nfl_state.get("week", 1) or 1
    user_id = user["user_id"]

    leagues, players_db = await asyncio.gather(
        get_leagues(user_id, season),
        get_players()
    )
    return user, nfl_state, season, current_week, leagues, players_db
