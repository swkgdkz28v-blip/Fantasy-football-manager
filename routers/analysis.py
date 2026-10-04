from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncio
from services.sleeper_client import *

router = APIRouter(prefix="/api", tags=["analysis"])

SLOT_ELIGIBILITY = {
    "QB": ["QB"], "RB": ["RB"], "WR": ["WR"], "TE": ["TE"],
    "K": ["K"], "DEF": ["DEF"],
    "FLEX": ["RB", "WR", "TE"],
    "SUPER_FLEX": ["QB", "RB", "WR", "TE"],
    "REC_FLEX": ["WR", "TE"],
    "WRRB_FLEX": ["WR", "RB"],
}

def round_weight(r: int) -> float:
    return {1: 10, 2: 5, 3: 2, 4: 1}.get(r, 0.5)

def player_name(p: dict) -> str:
    return f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()

def enrich_player(pid: str, players_db: dict, proj_map: dict, is_starter: bool) -> dict:
    p = players_db.get(str(pid))
    if not p:
        return None
    return {
        "id": str(pid),
        "name": player_name(p),
        "position": p.get("position", "UNK"),
        "team": p.get("team", "FA"),
        "age": p.get("age"),
        "years_exp": p.get("years_exp"),
        "injury_status": p.get("injury_status"),
        "pts": proj_map.get(str(pid), 0),
        "is_starter": is_starter,
    }

# ── REQUEST MODELS ────────────────────────────────────────────────────────────

class UserRequest(BaseModel):
    username: str
    week: Optional[int] = None

class UserLeagueRequest(BaseModel):
    username: str
    league_name: str
    week: Optional[int] = None

class WeekRequest(BaseModel):
    username: str
    week: int

# ── HEALTH ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok"}

# ── ALERTS ────────────────────────────────────────────────────────────────────

@router.post("/alerts/injured-starters")
async def get_injured_starters(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    week = req.week or current_week
    user_id = user["user_id"]
    results = []

    for league in leagues:
        rosters, matchups, league_users = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_matchups(league["league_id"], week),
            get_league_users(league["league_id"])
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        _mu = next((u for u in league_users if u["user_id"] == user_id), None)
        my_team_name = (_mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        starters = my_matchup.get("starters", []) if my_matchup else my_roster.get("starters", [])

        injured = []
        for pid in starters:
            p = players_db.get(str(pid))
            if not p:
                continue
            status = (p.get("injury_status") or "").lower()
            if status in ["out", "ir", "pup", "sus", "na"]:
                injured.append({"id": pid, "name": player_name(p), "position": p.get("position"), "team": p.get("team"), "status": p.get("injury_status")})

        if injured:
            results.append({"league": league["name"], "team": my_team_name, "injured": injured})

    return {"results": results}

@router.post("/alerts/questionable-starters")
async def get_questionable_starters(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    week = req.week or current_week
    user_id = user["user_id"]
    results = []

    for league in leagues:
        rosters, matchups, league_users = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_matchups(league["league_id"], week),
            get_league_users(league["league_id"])
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        _mu = next((u for u in league_users if u["user_id"] == user_id), None)
        my_team_name = (_mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        starters = my_matchup.get("starters", []) if my_matchup else my_roster.get("starters", [])

        questionable = []
        for pid in starters:
            p = players_db.get(str(pid))
            if not p:
                continue
            status = (p.get("injury_status") or "").lower()
            if status in ["doubtful", "questionable"]:
                questionable.append({"id": pid, "name": player_name(p), "position": p.get("position"), "team": p.get("team"), "status": p.get("injury_status")})

        if questionable:
            results.append({"league": league["name"], "team": my_team_name, "questionable": questionable})

    return {"results": results}

@router.post("/alerts/starters-on-bye")
async def get_starters_on_bye(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    week = req.week or current_week
    user_id = user["user_id"]
    results = []

    for league in leagues:
        rosters, matchups, league_users = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_matchups(league["league_id"], week),
            get_league_users(league["league_id"])
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        _mu = next((u for u in league_users if u["user_id"] == user_id), None)
        my_team_name = (_mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        starters = my_matchup.get("starters", []) if my_matchup else my_roster.get("starters", [])

        on_bye = []
        for pid in starters:
            p = players_db.get(str(pid))
            if not p:
                continue
            bye_week = p.get("bye_week")
            if bye_week and int(bye_week) == week:
                on_bye.append({"id": pid, "name": player_name(p), "position": p.get("position"), "team": p.get("team")})

        if on_bye:
            results.append({"league": league["name"], "team": my_team_name, "on_bye": on_bye})

    return {"results": results}

@router.post("/alerts/open-starter-spots")
async def get_open_starter_spots(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    week = req.week or current_week
    user_id = user["user_id"]
    results = []

    for league in leagues:
        rosters, matchups, league_users = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_matchups(league["league_id"], week),
            get_league_users(league["league_id"])
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        _mu = next((u for u in league_users if u["user_id"] == user_id), None)
        my_team_name = (_mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        starters = my_matchup.get("starters", []) if my_matchup else my_roster.get("starters", [])
        open_spots = [i for i, pid in enumerate(starters) if not pid or pid == "0"]
        if open_spots:
            results.append({"league": league["name"], "team": my_team_name, "open_slots": len(open_spots)})

    return {"results": results}

@router.post("/alerts/zero-projection-starters")
async def get_zero_projection_starters(req: UserRequest):
    """Starters projected for 0 points who have not played yet (bye, injured, no team, or no projection)."""
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    week = req.week or current_week
    user_id = user["user_id"]

    proj_array, stats_array = await asyncio.gather(get_projections(season, week), get_stats(season, week))
    stats_map = build_stats_map(stats_array)
    has_played = lambda pid: stats_map.get(str(pid), {}).get("gp", 0) >= 1

    results = []
    for league in leagues:
        if league.get("status") == "complete":
            continue
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        starter_slots = [x for x in league.get("roster_positions", []) if x not in ("BN", "IR", "TAXI")]

        rosters, league_users, matchups = await asyncio.gather(
            get_rosters(league["league_id"]), get_league_users(league["league_id"]), get_matchups(league["league_id"], week)
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        my_user = next((u for u in league_users if u["user_id"] == user_id), None)
        my_team_name = (my_user or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        starters = [str(x) for x in ((my_matchup or my_roster).get("starters") or [])]

        flagged = []
        for i, pid in enumerate(starters):
            if not pid or pid == "0":
                continue
            if has_played(pid):
                continue
            if proj_map.get(pid, 0) > 0:
                continue
            p = players_db.get(pid) or {}
            bye = p.get("bye_week")
            inj = (p.get("injury_status") or "").upper()
            team = p.get("team")
            if bye and int(bye) == week:
                reason = f"On bye (week {bye})"
            elif inj in ("OUT", "IR", "PUP", "SUS", "NA"):
                reason = f"Injury: {inj}"
            elif not team or team == "FA":
                reason = "No NFL team"
            elif inj:
                reason = f"No projection · {inj}"
            else:
                reason = "No projection"
            flagged.append({
                "slot": starter_slots[i] if i < len(starter_slots) else "?",
                "id": pid, "name": player_name(p) or pid, "position": p.get("position", "UNK"),
                "team": team or "FA", "status": reason, "injury_status": p.get("injury_status"),
            })
        if flagged:
            results.append({"league": league["name"], "team": my_team_name, "zero_starters": flagged})

    return {"week": week, "results": results}

# ── WEEK ANALYSIS ─────────────────────────────────────────────────────────────

@router.post("/analysis/week")
async def get_week_analysis(req: WeekRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week

    proj_array, stats_array = await asyncio.gather(
        get_projections(season, week),
        get_stats(season, week)
    )
    stats_map = build_stats_map(stats_array)
    results = []

    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)

        rosters, league_users, matchups = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_league_users(league["league_id"]),
            get_matchups(league["league_id"], week)
        )

        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        if not my_matchup:
            continue
        opp_matchup = next((m for m in matchups if m["matchup_id"] == my_matchup["matchup_id"] and m["roster_id"] != my_roster["roster_id"]), None)

        my_pts = my_matchup.get("points", 0)
        opp_pts = opp_matchup.get("points", 0) if opp_matchup else 0
        player_pts = my_matchup.get("players_points") or {}
        opp_player_pts = opp_matchup.get("players_points") or {} if opp_matchup else {}

        roster_lookup = {r["roster_id"]: r for r in rosters}
        user_lookup = {u["user_id"]: u for u in league_users}
        opp_roster = roster_lookup.get(opp_matchup["roster_id"]) if opp_matchup else None
        opp_user = user_lookup.get(opp_roster["owner_id"]) if opp_roster else None
        opp_name = (opp_user or {}).get("metadata", {}).get("team_name") or (opp_user or {}).get("display_name", "Opponent")

        def enrich_starters(starters, pts_map):
            result = []
            for pid in starters:
                if not pid or pid == "0":
                    continue
                p = players_db.get(str(pid))
                if not p:
                    continue
                actual = pts_map.get(str(pid), 0)
                st = stats_map.get(str(pid)) or {}
                result.append({
                    "id": pid,
                    "name": player_name(p),
                    "position": p.get("position"),
                    "team": p.get("team"),
                    "pts": actual,
                    "pass_yd": st.get("pass_yd", 0),
                    "pass_td": st.get("pass_td", 0),
                    "rush_yd": st.get("rush_yd", 0),
                    "rush_td": st.get("rush_td", 0),
                    "rec": st.get("rec", 0),
                    "rec_yd": st.get("rec_yd", 0),
                    "rec_td": st.get("rec_td", 0),
                })
            return sorted(result, key=lambda x: -x["pts"])

        my_starters = enrich_starters(my_matchup.get("starters", []), player_pts)
        opp_starters = enrich_starters(opp_matchup.get("starters", []), opp_player_pts) if opp_matchup else []

        # Optimal lineup
        roster_positions = league.get("roster_positions", [])
        starter_slots = [s for s in roster_positions if s not in ("BN", "IR", "TAXI")]
        taxi_ids = set(my_roster.get("taxi") or [])
        all_players = []
        for pid in (my_roster.get("players") or []):
            if str(pid) in taxi_ids:
                continue
            p = players_db.get(str(pid))
            if not p:
                continue
            pts = player_pts.get(str(pid), proj_map.get(str(pid), 0))
            all_players.append({
                "id": str(pid),
                "name": player_name(p),
                "position": p.get("position", "UNK"),
                "team": p.get("team", ""),
                "pts": pts,
            })
        all_players.sort(key=lambda x: -x.get("pts", 0))

        slots_sorted = sorted(starter_slots, key=lambda s: len(SLOT_ELIGIBILITY.get(s, [s])))
        assigned = set()
        optimal = []
        for slot in slots_sorted:
            eligible = SLOT_ELIGIBILITY.get(slot, [slot])
            best = next((p for p in all_players if p.get("position") in eligible and p["id"] not in assigned), None)
            if best:
                assigned.add(best["id"])
                optimal.append({"slot": slot, "player": best})

        optimal_pts = round(sum(o["player"]["pts"] for o in optimal), 2)
        gain = round(optimal_pts - my_pts, 2)

        _mu = user_lookup.get(user_id)
        my_team_name = (_mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        results.append({
            "league": league["name"],
            "team": my_team_name,
            "won": my_pts > opp_pts,
            "tied": my_pts == opp_pts,
            "my_pts": my_pts,
            "opp_pts": opp_pts,
            "opp_name": opp_name,
            "my_starters": my_starters,
            "opp_starters": opp_starters,
            "optimal_pts": optimal_pts,
            "optimal_gain": gain,
            "optimal": optimal,
        })

    return {"week": week, "results": results}

# ── WEEK RECORD ───────────────────────────────────────────────────────────────

@router.post("/analysis/week-record")
async def get_week_record(req: WeekRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week
    week_completed = week < current_week

    proj_array = await get_projections(season, week)
    results = []

    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)

        rosters, league_users, matchups = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_league_users(league["league_id"]),
            get_matchups(league["league_id"], week)
        )

        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        if not my_matchup:
            continue
        opp_matchup = next((m for m in matchups if m["matchup_id"] == my_matchup["matchup_id"] and m["roster_id"] != my_roster["roster_id"]), None)
        if not opp_matchup:
            continue

        user_lookup = {u["user_id"]: u for u in league_users}
        roster_lookup = {r["roster_id"]: r for r in rosters}
        opp_roster = roster_lookup.get(opp_matchup["roster_id"])
        opp_user = user_lookup.get(opp_roster["owner_id"]) if opp_roster else None
        opp_name = (opp_user or {}).get("metadata", {}).get("team_name") or (opp_user or {}).get("display_name", "Opponent")

        my_proj = round(sum(proj_map.get(str(pid), 0) for pid in my_matchup.get("starters", [])), 2)
        opp_proj = round(sum(proj_map.get(str(pid), 0) for pid in opp_matchup.get("starters", [])), 2)

        proj_win = my_proj > opp_proj
        proj_diff = my_proj - opp_proj
        win_prob = round(1 / (1 + 2.71828 ** (-proj_diff / 8)) * 100)

        actual_won = actual_tied = surprise = None
        my_actual = opp_actual = None
        if week_completed:
            my_actual = my_matchup.get("points", 0)
            opp_actual = opp_matchup.get("points", 0)
            actual_won = my_actual > opp_actual
            actual_tied = my_actual == opp_actual
            if (proj_win != actual_won) and abs(proj_diff) > 5:
                surprise = "upset_win" if actual_won else "upset_loss"

        _mu = user_lookup.get(user_id)
        my_team_name = (_mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        results.append({
            "league": league["name"],
            "team": my_team_name,
            "opp_name": opp_name,
            "my_proj": my_proj,
            "opp_proj": opp_proj,
            "proj_win": proj_win,
            "win_prob": win_prob,
            "my_actual": my_actual,
            "opp_actual": opp_actual,
            "actual_won": actual_won,
            "actual_tied": actual_tied,
            "surprise": surprise,
        })

    return {"week": week, "week_completed": week_completed, "results": results}

# ── THERE'S A CHANCE ──────────────────────────────────────────────────────────

@router.post("/analysis/theres-a-chance")
async def get_theres_a_chance(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week

    proj_array, stats_array = await asyncio.gather(
        get_projections(season, week),
        get_stats(season, week)
    )
    stats_map = build_stats_map(stats_array)
    IGNORE_THRESHOLD = 0.15
    results = []
    skipped = []

    for league in leagues:
        if league.get("status") == "complete":
            continue
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)

        rosters, league_users, matchups = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_league_users(league["league_id"]),
            get_matchups(league["league_id"], week)
        )

        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        if not my_matchup:
            continue
        opp_matchup = next((m for m in matchups if m["matchup_id"] == my_matchup["matchup_id"] and m["roster_id"] != my_roster["roster_id"]), None)
        if not opp_matchup:
            continue

        user_lookup = {u["user_id"]: u for u in league_users}
        roster_lookup = {r["roster_id"]: r for r in rosters}
        opp_roster = roster_lookup.get(opp_matchup["roster_id"])
        opp_user = user_lookup.get(opp_roster["owner_id"]) if opp_roster else None
        opp_name = (opp_user or {}).get("metadata", {}).get("team_name") or (opp_user or {}).get("display_name", "Opponent")

        my_live = my_matchup.get("points", 0)
        opp_live = opp_matchup.get("points", 0)
        my_player_pts = my_matchup.get("players_points") or {}
        opp_player_pts = opp_matchup.get("players_points") or {}

        def get_remaining(starters, player_pts):
            remaining = []
            for pid in starters:
                if not pid or pid == "0":
                    continue
                s = stats_map.get(str(pid)) or {}
                if s.get("gp", 0) >= 1:
                    continue  # already played
                p = players_db.get(str(pid)) or {}
                remaining.append({
                    "id": pid,
                    "name": player_name(p),
                    "position": p.get("position", "UNK"),
                    "team": p.get("team", ""),
                    "proj_pts": proj_map.get(str(pid), 0),
                })
            return remaining

        my_remaining = get_remaining(my_matchup.get("starters", []), my_player_pts)
        opp_remaining = get_remaining(opp_matchup.get("starters", []), opp_player_pts)

        my_remaining_proj = sum(p["proj_pts"] for p in my_remaining)
        opp_remaining_proj = sum(p["proj_pts"] for p in opp_remaining)
        my_max = round(my_live + my_remaining_proj, 2)
        opp_max = round(opp_live + opp_remaining_proj, 2)

        currently_winning = my_live >= opp_live
        if not currently_winning and opp_max > 0:
            deficit_pct = (opp_max - my_max) / opp_max
            if my_max < opp_max * (1 - IGNORE_THRESHOLD):
                _mu = user_lookup.get(user_id)
                skipped.append({"league": league["name"], "team": (_mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", ""),
                                "opp_name": opp_name, "my_live": my_live, "opp_live": opp_live, "my_max": my_max, "opp_max": opp_max})
                continue

        can_win_math = my_max > opp_live
        can_win_realistic = my_max > opp_max
        lead = my_live - opp_live

        if currently_winning and len(my_remaining) == 0 and len(opp_remaining) == 0:
            status = "WON"
        elif currently_winning and my_max > opp_max:
            status = "WINNING"
        elif currently_winning and my_max <= opp_max:
            status = "HOLD ON"
        elif not can_win_math:
            status = "ELIMINATED"
        elif can_win_realistic:
            status = "THERE'S A CHANCE"
        else:
            status = "LONG SHOT"

        _mu = user_lookup.get(user_id)
        my_team_name = (_mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        results.append({
            "league": league["name"],
            "team": my_team_name,
            "opp_name": opp_name,
            "my_live": my_live,
            "opp_live": opp_live,
            "my_max": my_max,
            "opp_max": opp_max,
            "my_remaining": my_remaining,
            "opp_remaining": opp_remaining,
            "my_remaining_proj": round(my_remaining_proj, 1),
            "opp_remaining_proj": round(opp_remaining_proj, 1),
            "status": status,
            "lead": round(lead, 2),
        })

    status_order = {"WON": 0, "WINNING": 1, "HOLD ON": 2, "THERE'S A CHANCE": 3, "LONG SHOT": 4, "ELIMINATED": 5}
    results.sort(key=lambda r: status_order.get(r["status"], 9))
    return {"results": results, "skipped": skipped}


# ── SHARED LINEUP HELPER ──────────────────────────────────────────────────────

def _assign_max_weight(W):
    """
    Max-weight assignment of rows -> columns (len(rows) <= len(cols)).
    Hungarian algorithm (O(n^2 m)). Returns col index for each row.
    """
    n = len(W)
    if n == 0:
        return []
    m = len(W[0])
    INF = float("inf")
    C = [[-w for w in row] for row in W]            # minimize negated weights
    u = [0.0] * (n + 1); v = [0.0] * (m + 1)
    p = [0] * (m + 1); way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i; j0 = 0
        minv = [INF] * (m + 1); used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = p[j0]; delta = INF; j1 = 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                cur = C[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur; way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]; j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta; v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]; p[j0] = p[j1]; j0 = j1
            if j0 == 0:
                break
    out = [-1] * n
    for j in range(1, m + 1):
        if p[j]:
            out[p[j] - 1] = j - 1
    return out


def compute_lineup(starter_slots, starters_ordered, pool, has_played, key="pts"):
    """
    starter_slots:    ordered slot names from league.roster_positions (BN/IR/TAXI removed)
    starters_ordered: matchup.starters — parallel to starter_slots (Sleeper's real slot order)
    pool:             all non-taxi rostered players, each with id/position/<key>
    has_played:       fn(pid) -> bool

    Rules:
      - A starter whose game is over is LOCKED into its slot.
      - A bench player whose game is over cannot be started.
      - Open slots are filled by an exact max-weight assignment, so QB/SUPER_FLEX
        and FLEX interactions are solved globally (a QB may move QB<->SF, etc.).
      - Ties break toward leaving a player in the slot they already occupy.
    Returns ordered list of {slot, current, optimal, locked}.
    """
    n = len(starter_slots)
    by_id = {p["id"]: p for p in pool}
    current = []
    for i in range(n):
        sid = str(starters_ordered[i]) if i < len(starters_ordered) else ""
        current.append(by_id.get(sid) if sid and sid != "0" else None)

    result = [None] * n
    locked_ids = set()
    for i in range(n):
        cur = current[i]
        if cur and has_played(cur["id"]):
            result[i] = {"slot": starter_slots[i], "current": cur, "optimal": cur, "locked": True}
            locked_ids.add(cur["id"])

    open_idx = [i for i in range(n) if result[i] is None]
    cands = [p for p in pool if p["id"] not in locked_ids and not has_played(p["id"])]

    if open_idx:
        NEG = -1e12
        k = len(cands)
        pad = len(open_idx)                       # one "leave empty" column per open slot
        W = []
        for i in open_idx:
            elig = SLOT_ELIGIBILITY.get(starter_slots[i], [starter_slots[i]])
            row = []
            for c in cands:
                if c["position"] in elig:
                    w = float(c.get(key, 0) or 0) * 10000.0
                    if current[i] and current[i]["id"] == c["id"]:
                        w += 1.0                  # stay-in-place tiebreak
                    row.append(w)
                else:
                    row.append(NEG)
            row.extend([0.0] * pad)
            W.append(row)
        assign = _assign_max_weight(W)
        for r, i in enumerate(open_idx):
            c = assign[r]
            pick = cands[c] if 0 <= c < k and W[r][c] > NEG / 2 else None
            result[i] = {"slot": starter_slots[i], "current": current[i], "optimal": pick, "locked": False}

    return result


def lineup_moves(lineup):
    """
    Turn a compute_lineup result into human moves:
      start: bench -> slot        bench: slot -> bench        move: slot -> slot
    Returns (moves, swaps) where swaps is the per-slot diff [{slot, out, in}].
    """
    cur_slot = {}; opt_slot = {}
    for s in lineup:
        if s["current"]:
            cur_slot[s["current"]["id"]] = s
        if s["optimal"]:
            opt_slot[s["optimal"]["id"]] = s
    moves = []
    for pid, s in opt_slot.items():
        if pid not in cur_slot:
            moves.append({"type": "start", "player": s["optimal"], "to_slot": s["slot"]})
        elif cur_slot[pid]["slot"] != s["slot"] or cur_slot[pid] is not s:
            if cur_slot[pid] is not s:
                moves.append({"type": "move", "player": s["optimal"], "from_slot": cur_slot[pid]["slot"], "to_slot": s["slot"]})
    for pid, s in cur_slot.items():
        if pid not in opt_slot and not s["locked"]:
            moves.append({"type": "bench", "player": s["current"], "from_slot": s["slot"]})
    order = {"start": 0, "move": 1, "bench": 2}
    moves.sort(key=lambda m: (order[m["type"]], -(m["player"].get("pts") or 0)))
    swaps = [{"slot": s["slot"], "out": s["current"], "in": s["optimal"]} for s in lineup
             if not s["locked"] and (s["optimal"] or {}).get("id") != (s["current"] or {}).get("id")]
    return moves, swaps

# ── OPTIMAL LINEUP ────────────────────────────────────────────────────────────

@router.post("/analysis/optimal-lineup")
async def get_optimal_lineup(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week

    weeks_completed = max(0, min(week - 1, current_week - 1))

    proj_array, stats_array = await asyncio.gather(get_projections(season, week), get_stats(season, week))
    stats_map = build_stats_map(stats_array)
    has_played = lambda pid: stats_map.get(str(pid), {}).get("gp", 0) >= 1

    # Season-to-date raw stats, summed per player (gp = games actually played)
    ytd = {}
    if weeks_completed > 0:
        for week_data in await asyncio.gather(*[get_stats(season, w) for w in range(1, weeks_completed + 1)]):
            for pid, st in build_stats_map(week_data).items():
                acc = ytd.setdefault(pid, {})
                for k, v in st.items():
                    if isinstance(v, (int, float)):
                        acc[k] = acc.get(k, 0) + v

    results, optimal_leagues = [], []

    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        starter_slots = [s for s in league.get("roster_positions", []) if s not in ("BN", "IR", "TAXI")]

        def season_avg(pid):
            """League-scored season points per game played. Returns (avg, gp)."""
            raw = ytd.get(pid)
            if not raw:
                return 0.0, 0
            gp = int(raw.get("gp", 0) or 0)
            if gp <= 0:
                return 0.0, 0
            total = sum(ss.get(k, 0) * v for k, v in raw.items())
            return round(total / gp, 1), gp

        rosters, league_users, matchups = await asyncio.gather(
            get_rosters(league["league_id"]), get_league_users(league["league_id"]), get_matchups(league["league_id"], week)
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        my_user = next((u for u in league_users if u["user_id"] == user_id), None)
        my_team_name = (my_user or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")

        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        starters_ordered = (my_matchup or my_roster).get("starters") or []
        actual_pts = (my_matchup or {}).get("players_points") or {}
        starter_set = set(str(s) for s in starters_ordered)
        taxi_ids = set(str(t) for t in (my_roster.get("taxi") or []))

        pool = []
        for pid in (my_roster.get("players") or []):
            pid = str(pid)
            if pid in taxi_ids:
                continue
            p = players_db.get(pid)
            if not p:
                continue
            played = has_played(pid)
            proj = round(proj_map.get(pid, 0), 1)
            avg, gp = season_avg(pid)
            # Ranking uses the week projection (actual points once a player has played);
            # season average / games played are informational only.
            pts = actual_pts.get(pid, 0) if played else proj
            pool.append({
                "id": pid, "name": player_name(p), "position": p.get("position", "UNK"), "team": p.get("team", "FA"),
                "pts": pts, "proj": proj, "avg": avg, "gp": gp,
                "has_played": played, "injury_status": p.get("injury_status"), "is_starter": pid in starter_set,
            })

        lineup = compute_lineup(starter_slots, starters_ordered, pool, has_played, key="pts")

        current_pts = round(sum((s["current"] or {}).get("pts", 0) for s in lineup), 2)
        optimal_pts = round(sum((s["optimal"] or {}).get("pts", 0) for s in lineup), 2)
        gain = round(optimal_pts - current_pts, 2)

        moves, swaps = lineup_moves(lineup)
        used = {s["optimal"]["id"] for s in lineup if s["optimal"]}
        bench = [p for p in pool if p["id"] not in used]

        if gain < 0.5 or not moves:
            optimal_leagues.append({"league": league["name"], "team": my_team_name, "pts": current_pts})
        else:
            results.append({
                "league": league["name"], "team": my_team_name,
                "optimal_pts": optimal_pts, "current_pts": current_pts, "gain": gain,
                "lineup": [{"slot": s["slot"], "player": s["optimal"], "locked": s["locked"]} for s in lineup],
                "moves": moves, "swaps": swaps, "bench": bench,
                "locked_count": sum(1 for s in lineup if s["locked"]),
            })

    return {"week": week, "weeks_completed": weeks_completed, "results": results, "optimal_leagues": optimal_leagues}

# ── MY POSITION NEEDS ─────────────────────────────────────────────────────────

@router.post("/analysis/position-needs")
async def get_position_needs(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]

    needs_by_pos = {pos: [] for pos in ["QB", "RB", "WR", "TE", "K", "DEF"]}
    ALL_POS = ["QB", "RB", "WR", "TE", "K", "DEF"]

    for league in leagues:
        roster_positions = league.get("roster_positions", [])
        dedicated_slots = {p: 0 for p in ALL_POS}
        flex_slots_list = []
        for slot in roster_positions:
            if slot in ("BN", "IR", "TAXI"):
                continue
            elig = SLOT_ELIGIBILITY.get(slot, [slot])
            if len(elig) == 1 and elig[0] in dedicated_slots:
                dedicated_slots[elig[0]] += 1
            else:
                flex_slots_list.append({"slot_type": slot, "eligible": elig})

        flex_slots_by_type = {}
        for fs in flex_slots_list:
            ft = fs["slot_type"]
            if ft not in flex_slots_by_type:
                flex_slots_by_type[ft] = {"count": 0, "eligible": fs["eligible"]}
            flex_slots_by_type[ft]["count"] += 1

        sf_count = flex_slots_by_type.get("SUPER_FLEX", {}).get("count", 0)
        qb_demand = dedicated_slots["QB"] + sf_count

        rosters, league_users = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_league_users(league["league_id"])
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue

        user_lookup = {u["user_id"]: u for u in league_users}
        my_user = user_lookup.get(user_id)
        my_team_name = (my_user or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")

        taxi_ids = set(my_roster.get("taxi") or [])
        players_by_pos = {pos: [] for pos in ALL_POS}
        for pid in my_roster.get("players", []):
            if str(pid) in taxi_ids:
                continue
            p = players_db.get(str(pid))
            if not p or p.get("position") not in ALL_POS:
                continue
            players_by_pos[p["position"]].append({"id": pid, "name": player_name(p), "team": p.get("team", "")})

        for pos in ALL_POS:
            dedicated = dedicated_slots[pos]
            pos_flex_slots = sum(1 for fs in flex_slots_list if pos in fs["eligible"])
            is_flex_eligible = pos_flex_slots > 0

            if dedicated == 0 and not is_flex_eligible:
                continue

            owned = len(players_by_pos[pos])

            # Flex demand is SHARED: each flex slot contributes 1/len(eligible) to every eligible position,
            # except SUPER_FLEX which is treated as a QB slot (QB is the dominant SF play).
            flex_share = 0.0
            for fs in flex_slots_list:
                if pos not in fs["eligible"]:
                    continue
                if fs["slot_type"] == "SUPER_FLEX":
                    flex_share += 1.0 if pos == "QB" else 0.0
                else:
                    flex_share += 1.0 / len(fs["eligible"])
            flex_need = int(flex_share + 0.5)          # round half up

            if pos == "QB":
                min_needed = dedicated + flex_need + 2   # QB depth matters more (bye/injury in SF)
            elif pos in ("RB", "WR", "TE"):
                min_needed = dedicated + flex_need + 1
            else:
                min_needed = dedicated

            if owned >= min_needed:
                continue

            if owned == 0 and dedicated > 0:
                grade = "Empty"
            elif owned < dedicated:
                grade = "Underfilled"
            elif owned < dedicated + flex_need:
                grade = "Flex Short"
            elif owned < min_needed:
                grade = "No Depth"
            else:
                grade = "Thin"

            format_notes = []
            if pos == "QB" and sf_count:
                format_notes.append(f"+{sf_count} Super Flex")
            if pos == "QB" and dedicated_slots["QB"] >= 2:
                format_notes.append("2QB league")
            flex_types = [f"{v['count']}× {ft}" if v['count'] > 1 else ft
                         for ft, v in flex_slots_by_type.items() if pos in v["eligible"]]
            if flex_types:
                format_notes.append(", ".join(flex_types))

            needs_by_pos[pos].append({
                "league": league["name"],
                "team": my_team_name,
                "owned": owned,
                "needed": dedicated,
                "flex_need": flex_need,
                "min_needed": min_needed,
                "grade": grade,
                "players": players_by_pos[pos],
                "format_notes": format_notes,
            })

    return {"needs_by_pos": {k: v for k, v in needs_by_pos.items() if v}}

# ── UPGRADE RECOMMENDATIONS ───────────────────────────────────────────────────

@router.post("/analysis/upgrade-recommendations")
async def get_upgrade_recommendations(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week
    weeks_completed = max(0, min(week - 1, current_week - 1))

    proj_array, stats_array = await asyncio.gather(get_projections(season, week), get_stats(season, week))
    stats_map = build_stats_map(stats_array)
    has_played = lambda pid: stats_map.get(str(pid), {}).get("gp", 0) >= 1

    ytd = {}
    if weeks_completed > 0:
        for week_data in await asyncio.gather(*[get_stats(season, w) for w in range(1, weeks_completed + 1)]):
            for pid, st in build_stats_map(week_data).items():
                acc = ytd.setdefault(pid, {})
                for k, v in st.items():
                    if isinstance(v, (int, float)):
                        acc[k] = acc.get(k, 0) + v

    results = []
    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        starter_slots = [s for s in league.get("roster_positions", []) if s not in ("BN", "IR", "TAXI")]

        def score(pid):
            """Returns (week_proj, season_avg_per_game_played, floor, games_played).
            floor = the LOWER of projection and season average — recommendations are
            conservative. Players with 0 games played fall back to projection."""
            wk = proj_map.get(pid, 0)
            raw = ytd.get(pid) or {}
            gp = int(raw.get("gp", 0) or 0)
            avg = sum(ss.get(k, 0) * v for k, v in raw.items()) / gp if gp > 0 else 0
            floor = min(wk, avg) if gp > 0 else wk
            return round(wk, 1), round(avg, 1), round(floor, 1), gp

        rosters, league_users, matchups = await asyncio.gather(
            get_rosters(league["league_id"]), get_league_users(league["league_id"]), get_matchups(league["league_id"], week)
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        my_user = next((u for u in league_users if u["user_id"] == user_id), None)
        my_team_name = (my_user or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")

        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        starters_ordered = (my_matchup or my_roster).get("starters") or []
        starter_set = set(str(s) for s in starters_ordered)
        taxi_ids = set(str(t) for t in (my_roster.get("taxi") or []))

        pool = []
        for pid in (my_roster.get("players") or []):
            pid = str(pid)
            if pid in taxi_ids:
                continue
            p = players_db.get(pid)
            if not p:
                continue
            wk, avg, bl, gp = score(pid)
            pool.append({
                "id": pid, "name": player_name(p), "position": p.get("position", "UNK"), "team": p.get("team", ""),
                "week_pts": wk, "ytd_avg": avg, "gp": gp, "blended": bl, "pts": bl,
                "has_played": has_played(pid), "is_starter": pid in starter_set,
            })

        lineup = compute_lineup(starter_slots, starters_ordered, pool, has_played, key="blended")
        current_pts = round(sum((s["current"] or {}).get("blended", 0) for s in lineup), 1)
        optimal_pts = round(sum((s["optimal"] or {}).get("blended", 0) for s in lineup), 1)
        moves, swaps = lineup_moves(lineup)
        used = {s["optimal"]["id"] for s in lineup if s["optimal"]}

        results.append({
            "league": league["name"], "team": my_team_name,
            "optimal_pts": optimal_pts, "current_pts": current_pts, "gain": round(optimal_pts - current_pts, 1),
            "moves": moves, "swaps": swaps,
            "lineup": [{"slot": s["slot"], "player": s["optimal"], "locked": s["locked"]} for s in lineup],
            "locked_count": sum(1 for s in lineup if s["locked"]),
            "bench": [p for p in pool if p["id"] not in used][:8],
        })

    return {"week": week, "weeks_completed": weeks_completed, "results": results}

# ── LEAGUE EVALUATION (shared by Overview + Tier Records) ─────────────────────

def _tier_of(c):
    if c > 4.0: return "Juggernaut", "#00e5a0", "👑"
    if c > 3.0: return "Contender", "#5c9eff", "🏆"
    if c > 2.0: return "Fringe", "#ffb347", "⚡"
    return "Rebuild", "#ff5c5c", "🔨"


def _evaluate_league(league, my_roster, rosters, traded_picks, players_db, proj_map, season, current_week):
    """Scores one league for the user. Returns a dict with both the blended composite
    (record included, used by Overview) and a roster-only composite (used by Tier Records)."""
    num_rounds = league.get("settings", {}).get("draft_rounds", 4)
    playoff_spots = league.get("settings", {}).get("playoff_teams", 6)
    playoff_week_start = league.get("settings", {}).get("playoff_week_start", 15)
    regular_season_weeks = max(1, playoff_week_start - 1)

    st = my_roster.get("settings") or {}
    wins, losses, ties = st.get("wins", 0), st.get("losses", 0), st.get("ties", 0)
    games_played = wins + losses + ties
    win_pct = (wins + 0.5 * ties) / games_played if games_played > 0 else 0
    fpts = st.get("fpts", 0) + st.get("fpts_decimal", 0) / 100.0
    fpa = st.get("fpts_against", 0) + st.get("fpts_against_decimal", 0) / 100.0

    def rk(r):
        rs = r.get("settings") or {}
        return (-rs.get("wins", 0), -(rs.get("fpts", 0) + rs.get("fpts_decimal", 0) / 100.0))
    sorted_rosters = sorted(rosters, key=rk)
    rank = next((i + 1 for i, r in enumerate(sorted_rosters) if r["roster_id"] == my_roster["roster_id"]), len(rosters))
    rank_pct = rank / len(rosters)
    in_playoffs = rank <= playoff_spots
    line_roster = sorted_rosters[playoff_spots - 1] if len(sorted_rosters) >= playoff_spots else sorted_rosters[-1]
    playoff_line_wins = (line_roster.get("settings") or {}).get("wins", 0)
    total_games_played = sum((r.get("settings") or {}).get("wins", 0) + (r.get("settings") or {}).get("losses", 0) for r in rosters)
    season_started = total_games_played > 0 or current_week > 1

    starter_ids = set(str(pid) for pid in (my_roster.get("starters") or []))
    taxi_ids = set(str(pid) for pid in (my_roster.get("taxi") or []))
    my_starters = [{"id": str(pid), "position": (players_db.get(str(pid)) or {}).get("position", ""),
                    "age": (players_db.get(str(pid)) or {}).get("age"), "pts": proj_map.get(str(pid), 0)}
                   for pid in (my_roster.get("players") or []) if str(pid) in starter_ids]
    my_bench = [{"pts": proj_map.get(str(pid), 0)} for pid in (my_roster.get("players") or [])
                if str(pid) not in starter_ids and str(pid) not in taxi_ids]

    league_avg = sum(sum(proj_map.get(str(pid), 0) for pid in (r.get("starters") or [])) for r in rosters) / len(rosters) if rosters else 0
    my_starter_pts = sum(p["pts"] for p in my_starters)
    pts_vs_avg = my_starter_pts / league_avg if league_avg > 0 else 1
    roster_score = 5 if pts_vs_avg >= 1.15 else 4 if pts_vs_avg >= 1.05 else 3 if pts_vs_avg >= 0.95 else 2 if pts_vs_avg >= 0.85 else 1

    starter_ages = [p["age"] for p in my_starters if p.get("age")]
    avg_age = sum(starter_ages) / len(starter_ages) if starter_ages else 26
    age_score = 5 if 25 <= avg_age <= 28 else 4 if avg_age <= 30 else 3 if avg_age >= 23 else 2

    next_season = str(int(season) + 1)
    picks_next = [p for p in traded_picks if p.get("season") == next_season]
    t_map = {f"{p['round']}-{p['roster_id']}": p["owner_id"] for p in picks_next}
    baseline_cap = sum(round_weight(r) for r in range(1, num_rounds + 1))
    my_cap, missing_rounds = 0, []
    for rnd in range(1, num_rounds + 1):
        owned_count = sum(1 for r in rosters if t_map.get(f"{rnd}-{r['roster_id']}", r["roster_id"]) == my_roster["roster_id"])
        if t_map.get(f"{rnd}-{my_roster['roster_id']}", my_roster["roster_id"]) != my_roster["roster_id"]:
            missing_rounds.append(rnd)
        my_cap += owned_count * round_weight(rnd)
    cap_ratio = my_cap / baseline_cap if baseline_cap > 0 else 1
    draft_score = 5 if cap_ratio >= 1.8 else 4 if cap_ratio >= 1.4 else 3 if cap_ratio >= 0.9 else 2 if cap_ratio >= 0.5 else 1
    if 1 in missing_rounds:
        draft_score = min(draft_score, 2)
    if 1 in missing_rounds and 2 in missing_rounds:
        draft_score = 1

    depth_count = sum(1 for p in my_bench if p["pts"] >= 5)
    depth_score = 5 if depth_count >= 6 else 4 if depth_count >= 4 else 3 if depth_count >= 2 else 2 if depth_count >= 1 else 1

    record_score = 3
    if season_started and games_played > 0:
        wp_score = 5 if win_pct >= 0.70 else 4 if win_pct >= 0.55 else 3 if win_pct >= 0.45 else 2 if win_pct >= 0.30 else 1
        rank_score = 5 if rank_pct <= 0.20 else 4 if rank_pct <= 0.40 else 3 if rank_pct <= 0.60 else 2 if rank_pct <= 0.80 else 1
        sp = games_played / regular_season_weeks
        record_score = max(1, min(5, round(wp_score * (1 - sp * 0.4) + rank_score * (sp * 0.4 + 0.3))))

    roster_composite = roster_score * 0.75 + draft_score * 0.15 + age_score * 0.05 + depth_score * 0.05
    if season_started and games_played > 0:
        sp = min(games_played / regular_season_weeks, 1)
        rec_w = 0.20 * sp
        composite = roster_score * (0.75 - rec_w * 0.5) + record_score * rec_w + draft_score * (0.15 - rec_w * 0.3) + age_score * 0.05 + depth_score * 0.05
    else:
        composite = roster_composite

    tier, tier_color, tier_icon = _tier_of(composite)
    roster_tier, roster_tier_color, roster_tier_icon = _tier_of(roster_composite)

    if composite > 4.0 or (composite > 3.0 and record_score >= 4):
        strategy, strat_color, strat_icon = "Win Now", "#00e5a0", "🔥"
        strat_actions = ["Trade depth and picks for proven starters", "Target aging veterans who want to win now", "Prioritize win-now FAs over upside fliers", "Don't hoard picks — use them as currency"]
    elif composite > 3.0 and record_score < 3:
        strategy, strat_color, strat_icon = "Sell High", "#5c9eff", "📈"
        strat_actions = ["Your roster is stronger than your record — trade from hidden strength", "Other teams undervalue you right now — capitalize", "Sell players at peak value before the market corrects", "Look to acquire assets from teams overrating their hot start"]
    elif composite <= 2.0:
        strategy, strat_color, strat_icon = "Full Rebuild", "#ff5c5c", "🔨"
        strat_actions = ["Sell aging veterans (28+) for picks or young players", "Acquire as many first round picks as possible", "Target youth with high upside on waivers", "Don't trade future picks for win-now pieces"]
    elif composite > 2.0 and record_score >= 4:
        strategy, strat_color, strat_icon = "Trust the Process", "#ff8c42", "⏳"
        strat_actions = ["Your record is outpacing your roster — be cautious", "Don't overpay to win now on a middling roster", "Sell high on players performing above projection", "Build depth while momentum is with you"]
    else:
        strategy, strat_color, strat_icon = "Patience", "#ffb347", "🎯"
        strat_actions = ["Identify your 1-2 weakest positions and target specific upgrades", "Avoid trading multiple picks for one player", "Stay active on waivers — consistency beats big swings", "Monitor contenders for buy-low opportunities after losses"]

    return {
        "wins": wins, "losses": losses, "ties": ties, "games_played": games_played, "win_pct": round(win_pct, 3),
        "fpts": round(fpts, 2), "fpa": round(fpa, 2),
        "rank": rank, "total_teams": len(rosters), "in_playoffs": in_playoffs, "playoff_spots": playoff_spots,
        "playoff_line_wins": playoff_line_wins, "regular_season_weeks": regular_season_weeks,
        "season_started": season_started,
        "scores": {"Roster": roster_score, "Draft": draft_score, "Age": age_score, "Depth": depth_score, "Record": record_score},
        "composite": round(composite, 2), "tier": tier, "tier_color": tier_color, "tier_icon": tier_icon,
        "roster_composite": round(roster_composite, 2), "roster_tier": roster_tier,
        "roster_tier_color": roster_tier_color, "roster_tier_icon": roster_tier_icon,
        "strategy": strategy, "strat_color": strat_color, "strat_icon": strat_icon, "strat_actions": strat_actions,
        "avg_age": round(avg_age, 1), "starter_pts": round(my_starter_pts, 1), "pts_vs_avg": round(pts_vs_avg, 3),
        "missing_rounds": missing_rounds, "cap_ratio": round(cap_ratio, 2),
    }


async def _evaluate_all(req_username, week_override=None):
    """Fetches + evaluates every league. Returns (user, season, current_week, [(league, my_team_name, eval)])."""
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req_username)
    user_id = user["user_id"]
    week = week_override or current_week
    proj_array = await get_projections(season, week)
    out = []
    for league in leagues:
        proj_map = build_proj_map(proj_array, league.get("scoring_settings") or {})
        rosters, league_users, traded_picks = await asyncio.gather(
            get_rosters(league["league_id"]), get_league_users(league["league_id"]), get_traded_picks(league["league_id"])
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        my_user = next((u for u in league_users if u["user_id"] == user_id), None)
        my_team_name = (my_user or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        ev = _evaluate_league(league, my_roster, rosters, traded_picks, players_db, proj_map, season, current_week)
        out.append((league, my_team_name, ev))
    return user, season, current_week, out


# ── OVERVIEW (Contender + Strategy) ───────────────────────────────────────────

@router.post("/analysis/overview")
async def get_overview(req: UserRequest):
    user, season, current_week, evals = await _evaluate_all(req.username, req.week)
    results = []
    for league, my_team_name, ev in evals:
        results.append({
            "league": league["name"], "team": my_team_name,
            "record": f"{ev['wins']}-{ev['losses']}" + (f"-{ev['ties']}" if ev["ties"] else ""),
            "rank": ev["rank"], "total_teams": ev["total_teams"], "in_playoffs": ev["in_playoffs"],
            "composite": ev["composite"], "tier": ev["tier"], "tier_color": ev["tier_color"], "tier_icon": ev["tier_icon"],
            "strategy": ev["strategy"], "strat_color": ev["strat_color"], "strat_icon": ev["strat_icon"],
            "strat_actions": ev["strat_actions"], "scores": ev["scores"],
            "avg_age": ev["avg_age"], "starter_pts": ev["starter_pts"], "pts_vs_avg": ev["pts_vs_avg"],
        })
    results.sort(key=lambda r: {"Win Now": 0, "Sell High": 1, "Patience": 2, "Trust the Process": 3, "Full Rebuild": 4}.get(r["strategy"], 9))
    return {"results": results}


# ── TIER RECORDS (are my tiers earning their record?) ─────────────────────────

PYTH_EXP = 2.37   # Pythagorean exponent tuned for fantasy scoring variance

def _tier_record_verdict(ev):
    """
    Compares the ROSTER tier (record excluded) against the actual record and
    returns a status + forward recommendation.
    """
    tier = ev["roster_tier"]
    gp, wins, ties = ev["games_played"], ev["wins"], ev["ties"]
    wp = ev["win_pct"]
    rsw = ev["regular_season_weeks"]
    games_left = max(0, rsw - gp)
    progress = gp / rsw if rsw else 0

    exp_wp = None; exp_wins = None; luck = None
    if ev["fpts"] > 0 and ev["fpa"] > 0 and gp > 0:
        exp_wp = ev["fpts"] ** PYTH_EXP / (ev["fpts"] ** PYTH_EXP + ev["fpa"] ** PYTH_EXP)
        exp_wins = round(exp_wp * gp, 1)
        luck = round(wins + 0.5 * ties - exp_wins, 1)

    games_back = 0 if ev["in_playoffs"] else max(0, ev["playoff_line_wins"] - wins)
    reachable = games_back == 0 or games_back < games_left   # tied on games needs a tiebreak; equal = need a miracle

    A = {}  # status -> (color, headline, actions)
    A["PRESEASON"]    = ("#8b91a8", "No games played yet — nothing to judge.", [])
    A["ON TRACK"]     = ("#00e5a0", "Roster tier and record agree. Stay the course.",
                         ["Keep the lineup tight — no reason to churn", "Buy low from contenders coming off 2–3 straight losses", "Don't overpay for marginal upgrades"])
    A["HOLD — UNLUCKY"] = ("#ffb347", "Elite roster, losing record, but points say you should be winning. It's early — do not blow it up.",
                         ["Hold every core piece; the record will regress toward your points", "Use the perception dip: buy one more starter from a panicking rival", "Audit lineup decisions — was it luck or bench points?"])
    A["RETOOL"]       = ("#ff8c42", "Roster says contender, record says no, and it's no longer early. Move 1–2 pieces while their value holds — keep the core.",
                         ["Sell your oldest high-value starter (28+) for a younger starter + pick", "Fix the single weakest lineup slot via trade, not waivers", "Set a hard deadline: if still under .500 in 2 weeks, go to fire sale"])
    A["LAST CALL"]    = ("#ff5c5c", "Late season, under .500, playoffs still mathematically reachable. Decide this week: all-in or sell.",
                         ["Within 1 game of the line: buy one difference-maker for picks", "More than 1 game back: start the fire sale now, before other sellers flood the market", "Stop spending FAAB on rentals"])
    A["FIRE SALE"]    = ("#ff5c5c", "Strong roster, losing record, and the playoffs are out of reach. Convert value into futures before it decays.",
                         ["Sell every starter 27+ with real trade value for 1st-round picks or players ≤24", "Move RBs first — RB value decays fastest", "Target the next-year 1sts of teams sitting 2nd–4th: they think they're contending", "Don't spend FAAB on win-now pickups; stash youth"])
    A["OVERACHIEVING"]= ("#5c9eff", "Middling roster with a winning record. Enjoy it, but sell into it — don't buy.",
                         ["Sell any player scoring well above projection", "Don't trade picks to 'push' — the roster doesn't support it", "Bank the wins; use them as leverage in trade talks"])
    A["PIVOT TO REBUILD"] = ("#ff5c5c", "Middling roster, losing record, playoffs gone. This is the moment to commit to a rebuild.",
                         ["Sell all vets 27+ for picks", "Accumulate next-year 1sts and 2nds", "Prioritize youth on waivers over any win-now pickup"])
    A["ON SCHEDULE"]  = ("#8b91a8", "Rebuilding and losing — that's the plan. Keep accumulating.",
                         ["Keep selling vets on hot streaks", "Target rookies and 2nd-year players on waivers", "Don't get tempted into win-now trades"])
    A["AHEAD OF SCHEDULE"] = ("#5c9eff", "Rebuilding roster with a winning record. Don't abandon the plan for a hot start — sell into it.",
                         ["Sell the vets driving the wins while their value is inflated", "Don't trade future picks to chase a fluke season", "If still winning at midseason, re-evaluate — but stay disciplined"])

    if gp == 0:
        status = "PRESEASON"
    elif tier in ("Juggernaut", "Contender"):
        if wp >= 0.5:
            status = "ON TRACK"
        elif not reachable:
            status = "FIRE SALE"
        elif progress < 0.4 and luck is not None and luck <= -0.75:
            status = "HOLD — UNLUCKY"
        elif progress < 0.6:
            status = "RETOOL"
        else:
            status = "LAST CALL"
    elif tier == "Fringe":
        if wp >= 0.5:
            status = "OVERACHIEVING"
        elif not reachable:
            status = "PIVOT TO REBUILD"
        else:
            status = "RETOOL"
    else:  # Rebuild
        status = "ON SCHEDULE" if wp < 0.5 else "AHEAD OF SCHEDULE"

    color, headline, actions = A[status]
    flagged = status in ("FIRE SALE", "RETOOL", "LAST CALL", "HOLD — UNLUCKY", "PIVOT TO REBUILD")
    return {
        "status": status, "status_color": color, "headline": headline, "actions": actions, "flagged": flagged,
        "exp_win_pct": round(exp_wp, 3) if exp_wp is not None else None,
        "exp_wins": exp_wins, "luck": luck,
        "games_left": games_left, "games_back": games_back, "reachable": reachable, "progress": round(progress, 2),
    }


@router.post("/analysis/tier-records")
async def get_tier_records(req: UserRequest):
    user, season, current_week, evals = await _evaluate_all(req.username, req.week)
    results = []
    for league, my_team_name, ev in evals:
        v = _tier_record_verdict(ev)
        results.append({
            "league": league["name"], "team": my_team_name,
            "record": f"{ev['wins']}-{ev['losses']}" + (f"-{ev['ties']}" if ev["ties"] else ""),
            "wins": ev["wins"], "losses": ev["losses"], "ties": ev["ties"], "games_played": ev["games_played"], "win_pct": ev["win_pct"],
            "fpts": ev["fpts"], "fpa": ev["fpa"],
            "rank": ev["rank"], "total_teams": ev["total_teams"], "in_playoffs": ev["in_playoffs"], "playoff_spots": ev["playoff_spots"],
            "tier": ev["roster_tier"], "tier_color": ev["roster_tier_color"], "tier_icon": ev["roster_tier_icon"],
            "roster_composite": ev["roster_composite"], "blended_tier": ev["tier"],
            "scores": ev["scores"], "avg_age": ev["avg_age"], "pts_vs_avg": ev["pts_vs_avg"],
            **v,
        })

    tier_order = {"Juggernaut": 0, "Contender": 1, "Fringe": 2, "Rebuild": 3}
    results.sort(key=lambda r: (tier_order.get(r["tier"], 9), r["win_pct"], -r["roster_composite"]))

    by_tier = {}
    for r in results:
        t = by_tier.setdefault(r["tier"], {"tier": r["tier"], "color": r["tier_color"], "icon": r["tier_icon"],
                                          "leagues": 0, "wins": 0, "losses": 0, "ties": 0, "flagged": 0, "under_500": 0})
        t["leagues"] += 1; t["wins"] += r["wins"]; t["losses"] += r["losses"]; t["ties"] += r["ties"]
        t["flagged"] += 1 if r["flagged"] else 0
        t["under_500"] += 1 if r["games_played"] > 0 and r["win_pct"] < 0.5 else 0
    for t in by_tier.values():
        g = t["wins"] + t["losses"] + t["ties"]
        t["win_pct"] = round((t["wins"] + 0.5 * t["ties"]) / g, 3) if g else None

    summary = {
        "leagues": len(results),
        "flagged": sum(1 for r in results if r["flagged"]),
        "fire_sale": sum(1 for r in results if r["status"] in ("FIRE SALE", "PIVOT TO REBUILD")),
        "on_track": sum(1 for r in results if r["status"] in ("ON TRACK", "ON SCHEDULE")),
        "overachieving": sum(1 for r in results if r["status"] in ("OVERACHIEVING", "AHEAD OF SCHEDULE")),
        "by_tier": [by_tier[t] for t in ("Juggernaut", "Contender", "Fringe", "Rebuild") if t in by_tier],
    }
    return {"week": current_week, "summary": summary, "results": results}


# ── TEAM DEEP DIVE (one league, one team, everything) ─────────────────────────

def _grade(ratio):
    return "A" if ratio >= 1.15 else "B" if ratio >= 1.05 else "C" if ratio >= 0.95 else "D" if ratio >= 0.85 else "F"

def _win_prob(diff):
    return round(1 / (1 + 2.71828 ** (-diff / 8)) * 100)


@router.post("/analysis/team-deep-dive")
async def get_team_deep_dive(req: UserLeagueRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week
    q = (req.league_name or "").strip().lower()
    if not q:
        raise HTTPException(status_code=400, detail="League name is required for a deep dive")

    league = next((l for l in leagues if l["name"].strip().lower() == q), None) \
          or next((l for l in leagues if q in l["name"].lower()), None)
    if not league:
        raise HTTPException(status_code=404, detail=f'No league matching "{req.league_name}". Your leagues: ' + ", ".join(l["name"] for l in leagues))

    ss = league.get("scoring_settings") or {}
    roster_positions = league.get("roster_positions", [])
    starter_slots = [x for x in roster_positions if x not in ("BN", "IR", "TAXI")]
    playoff_week_start = league.get("settings", {}).get("playoff_week_start", 15)
    reg_end = playoff_week_start - 1
    num_rounds = league.get("settings", {}).get("draft_rounds", 4)
    is_dynasty = league.get("settings", {}).get("type", 0) == 2
    scoring_type = "PPR" if ss.get("rec", 0) >= 1 else "Half PPR" if ss.get("rec", 0) >= 0.5 else "Standard"
    weeks_done = max(0, min(week, current_week) - 1)

    # ── fetch everything for this league in parallel ──
    past_weeks = list(range(1, weeks_done + 1))
    future_weeks = list(range(week, reg_end + 1))
    fetches = [get_rosters(league["league_id"]), get_league_users(league["league_id"]), get_traded_picks(league["league_id"]),
               get_projections(season, week), get_stats(season, week)]
    fetches += [get_matchups(league["league_id"], w) for w in past_weeks + future_weeks]
    fetches += [get_stats(season, w) for w in past_weeks]
    res = await asyncio.gather(*fetches)
    rosters, league_users, traded_picks, proj_array, stats_array = res[:5]
    mu = res[5:5 + len(past_weeks) + len(future_weeks)]
    past_matchups = dict(zip(past_weeks, mu[:len(past_weeks)]))
    future_matchups = dict(zip(future_weeks, mu[len(past_weeks):]))
    past_stats = dict(zip(past_weeks, res[5 + len(mu):]))

    my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
    if not my_roster:
        raise HTTPException(status_code=404, detail=f"You don't have a team in {league['name']}")
    user_lookup = {u["user_id"]: u for u in league_users}
    roster_lookup = {r["roster_id"]: r for r in rosters}
    def team_name_of(roster):
        u = user_lookup.get((roster or {}).get("owner_id"))
        return (u or {}).get("metadata", {}).get("team_name") or (u or {}).get("display_name") or f"Roster {(roster or {}).get('roster_id')}"
    my_team_name = team_name_of(my_roster)

    proj_map = build_proj_map(proj_array, ss)
    stats_map = build_stats_map(stats_array)
    has_played = lambda pid: stats_map.get(str(pid), {}).get("gp", 0) >= 1

    # ── evaluation + verdict (same engine as Overview / Tier Records) ──
    ev = _evaluate_league(league, my_roster, rosters, traded_picks, players_db, proj_map, season, current_week)
    verdict = _tier_record_verdict(ev)

    # ── YTD per player (league scoring) ──
    ytd = {}
    for w, arr in past_stats.items():
        for pid, st in build_stats_map(arr).items():
            acc = ytd.setdefault(pid, {"pts": 0.0, "gp": 0})
            acc["pts"] += sum(ss.get(k, 0) * v for k, v in st.items() if isinstance(v, (int, float)))
            acc["gp"] += 1 if st.get("gp", 0) >= 1 else 0

    # ── roster ──
    my_matchup = next((m for m in (future_matchups.get(week) or past_matchups.get(week) or []) if m["roster_id"] == my_roster["roster_id"]), None)
    starters_ordered = [str(x) for x in ((my_matchup or my_roster).get("starters") or [])]
    starter_set = set(starters_ordered)
    taxi_ids = set(str(x) for x in (my_roster.get("taxi") or []))
    reserve_ids = set(str(x) for x in (my_roster.get("reserve") or []))
    slot_of = {}
    for i, pid in enumerate(starters_ordered):
        if pid and pid != "0" and i < len(starter_slots):
            slot_of[pid] = starter_slots[i]

    roster = []
    for pid in (my_roster.get("players") or []):
        pid = str(pid)
        p = players_db.get(pid)
        if not p:
            continue
        y = ytd.get(pid, {"pts": 0.0, "gp": 0})
        roster.append({
            "id": pid, "name": player_name(p), "position": p.get("position", "UNK"), "team": p.get("team") or "FA",
            "age": p.get("age"), "years_exp": p.get("years_exp"), "injury_status": p.get("injury_status"),
            "bye_week": p.get("bye_week"), "proj": proj_map.get(pid, 0),
            "ytd_pts": round(y["pts"], 1), "ytd_gp": y["gp"], "ytd_avg": round(y["pts"] / y["gp"], 1) if y["gp"] else 0,
            "role": "taxi" if pid in taxi_ids else "ir" if pid in reserve_ids else "starter" if pid in starter_set else "bench",
            "slot": slot_of.get(pid), "has_played": has_played(pid),
        })
    roster.sort(key=lambda x: (-(x["role"] == "starter"), x["position"], -x["proj"]))

    # ── position groups vs league ──
    POS = ["QB", "RB", "WR", "TE", "K", "DEF"]
    lg_pos_avg = {}
    for pos in POS:
        vals = []
        for r in rosters:
            pts = [proj_map.get(str(x), 0) for x in (r.get("starters") or []) if (players_db.get(str(x)) or {}).get("position") == pos]
            if pts:
                vals.append(sum(pts) / len(pts))
        lg_pos_avg[pos] = sum(vals) / len(vals) if vals else 0
    position_groups = []
    for pos in POS:
        mine = [x for x in roster if x["position"] == pos and x["role"] != "taxi"]
        if not mine and lg_pos_avg[pos] == 0:
            continue
        st = [x for x in mine if x["role"] == "starter"]
        my_avg = sum(x["proj"] for x in st) / len(st) if st else 0
        ratio = my_avg / lg_pos_avg[pos] if lg_pos_avg[pos] > 0 else (1 if st else 0)
        dedicated = sum(1 for x in starter_slots if x == pos)
        flex_el = sum(1 for x in starter_slots if x != pos and pos in SLOT_ELIGIBILITY.get(x, []))
        startable_depth = sum(1 for x in mine if x["role"] == "bench" and x["proj"] >= lg_pos_avg[pos] * 0.8)
        starter_quality = sum(1 for x in mine if x["role"] in ("starter", "bench") and lg_pos_avg[pos] > 0 and x["proj"] >= lg_pos_avg[pos] * 0.9)
        position_groups.append({
            "position": pos, "grade": _grade(ratio) if st else ("F" if dedicated else "—"),
            "my_avg": round(my_avg, 1), "league_avg": round(lg_pos_avg[pos], 1), "ratio": round(ratio, 2),
            "count": len(mine), "starters": len(st), "dedicated_slots": dedicated, "flex_slots": flex_el,
            "startable_depth": startable_depth, "starter_quality": starter_quality,
            "surplus": starter_quality > dedicated + 1,
            "need": (ratio < 0.9 and dedicated > 0) or (dedicated > 0 and not st),
            "players": mine,
        })

    # ── this week's lineup ──
    pool = [{"id": x["id"], "name": x["name"], "position": x["position"], "team": x["team"], "pts": x["proj"],
             "injury_status": x["injury_status"], "is_starter": x["role"] == "starter"} for x in roster if x["role"] in ("starter", "bench")]
    lineup = compute_lineup(starter_slots, starters_ordered, pool, has_played, key="pts")
    moves, _ = lineup_moves(lineup)
    cur_pts = round(sum((x["current"] or {}).get("pts", 0) for x in lineup), 1)
    opt_pts = round(sum((x["optimal"] or {}).get("pts", 0) for x in lineup), 1)
    zero_starters = [x for x in roster if x["role"] == "starter" and x["proj"] <= 0 and not x["has_played"]]
    injured_starters = [x for x in roster if x["role"] == "starter" and (x["injury_status"] or "").lower() in ("out", "ir", "pup", "sus", "doubtful")]

    # ── season log with hindsight efficiency ──
    log = []
    for w in past_weeks:
        ms = past_matchups.get(w) or []
        m = next((x for x in ms if x["roster_id"] == my_roster["roster_id"]), None)
        if not m:
            continue
        opp = next((x for x in ms if x.get("matchup_id") == m.get("matchup_id") and x["roster_id"] != m["roster_id"]), None)
        pp = m.get("players_points") or {}
        wk_pool = [{"id": str(pid), "position": (players_db.get(str(pid)) or {}).get("position", "UNK"), "pts": pp.get(str(pid), 0)}
                   for pid in (m.get("players") or [])]
        st_ordered = [str(x) for x in (m.get("starters") or [])]
        hind = compute_lineup(starter_slots, st_ordered, wk_pool, lambda pid: False, key="pts")
        optimal = round(sum((x["optimal"] or {}).get("pts", 0) for x in hind), 2)
        mine = round(m.get("points", 0) or 0, 2)
        oppp = round(opp.get("points", 0) or 0, 2) if opp else None
        if mine == 0 and (oppp or 0) == 0:
            continue                       # week not scored (data missing) — don't count it
        tied = oppp is not None and mine == oppp
        won = None if (oppp is None or tied) else (mine > oppp)
        log.append({
            "week": w, "my_pts": mine, "opp_pts": oppp, "opp_name": team_name_of(roster_lookup.get((opp or {}).get("roster_id"))),
            "won": won, "tied": tied, "optimal_pts": optimal,
            "left_on_bench": round(max(0, optimal - mine), 2),
            "efficiency": round(mine / optimal * 100, 1) if optimal > 0 else 100.0,
            "cost_the_game": bool(won is False and oppp is not None and optimal > oppp),
        })
    total_left = round(sum(x["left_on_bench"] for x in log), 1)
    games_cost = sum(1 for x in log if x["cost_the_game"])
    avg_eff = round(sum(x["efficiency"] for x in log) / len(log), 1) if log else None

    # ── remaining schedule ──
    strength = {r["roster_id"]: sum(proj_map.get(str(x), 0) for x in (r.get("starters") or [])) for r in rosters}
    my_strength = sum(proj_map.get(x, 0) for x in starters_ordered if x and x != "0") or strength.get(my_roster["roster_id"], 0)
    schedule = []
    for w in future_weeks:
        ms = future_matchups.get(w) or []
        m = next((x for x in ms if x["roster_id"] == my_roster["roster_id"]), None)
        if not m:
            continue
        opp = next((x for x in ms if x.get("matchup_id") == m.get("matchup_id") and x["roster_id"] != m["roster_id"]), None)
        if not opp:
            continue
        opp_r = roster_lookup.get(opp["roster_id"]) or {}
        os_ = opp_r.get("settings") or {}
        opp_str = strength.get(opp["roster_id"], 0)
        schedule.append({
            "week": w, "opp_name": team_name_of(opp_r), "opp_record": f"{os_.get('wins', 0)}-{os_.get('losses', 0)}",
            "my_proj": round(my_strength, 1), "opp_proj": round(opp_str, 1),
            "win_prob": _win_prob(my_strength - opp_str), "is_current": w == week,
        })
    exp_remaining_wins = round(sum(x["win_prob"] for x in schedule) / 100, 1)
    proj_final_wins = round(ev["wins"] + exp_remaining_wins, 1)
    proj_final_losses = round(ev["losses"] + len(schedule) - exp_remaining_wins, 1)
    sched_strength = round(sum(x["opp_proj"] for x in schedule) / len(schedule), 1) if schedule else None
    lg_avg_strength = round(sum(strength.values()) / len(strength), 1) if strength else None

    # ── draft capital (next season) ──
    next_season = str(int(season) + 1)
    t_map = {f"{p['round']}-{p['roster_id']}": p["owner_id"] for p in traded_picks if p.get("season") == next_season}
    picks = []
    for rnd in range(1, num_rounds + 1):
        for r in rosters:
            owner = t_map.get(f"{rnd}-{r['roster_id']}", r["roster_id"])
            if owner == my_roster["roster_id"]:
                picks.append({"round": rnd, "original_owner": team_name_of(r), "own": r["roster_id"] == my_roster["roster_id"]})
    traded_away = [{"round": rnd, "to": team_name_of(roster_lookup.get(t_map[f"{rnd}-{my_roster['roster_id']}"]))}
                   for rnd in range(1, num_rounds + 1)
                   if t_map.get(f"{rnd}-{my_roster['roster_id']}", my_roster["roster_id"]) != my_roster["roster_id"]]

    # ── trade assets ──
    def is_vet(x):
        a = x.get("age") or 0
        return a >= 26 if x["position"] == "RB" else a >= 27
    sell_candidates = sorted(
        [x for x in roster if x["role"] in ("starter", "bench") and is_vet(x) and x["proj"] >= lg_pos_avg.get(x["position"], 0) * 0.9 and x["proj"] > 0],
        key=lambda x: -x["proj"])[:6]
    young_core = sorted(
        [x for x in roster if (x.get("age") or 99) <= 25 and x["proj"] >= lg_pos_avg.get(x["position"], 0) * 0.9 and x["proj"] > 0],
        key=lambda x: -x["proj"])[:6]
    needs = [g["position"] for g in position_groups if g["need"]]
    surplus = [g["position"] for g in position_groups if g["surplus"]]

    # ── deep-dive verdict text: reuse tier verdict + specifics ──
    specifics = []
    if verdict["status"] in ("FIRE SALE", "PIVOT TO REBUILD") and sell_candidates:
        specifics.append("Sell first: " + ", ".join(f"{x['name']} ({x['position']}, {x['age']})" for x in sell_candidates[:3]))
    if verdict["status"] in ("RETOOL", "LAST CALL") and needs:
        specifics.append("Fix via trade: " + ", ".join(needs) + (f" — pay with {', '.join(surplus)} depth" if surplus else ""))
    if verdict["status"] == "HOLD — UNLUCKY" and total_left >= 10:
        specifics.append(f"{total_left} pts left on the bench this season — some of the 'bad luck' is lineup management")
    if games_cost:
        specifics.append(f"Lineup decisions cost {games_cost} game{'s' if games_cost != 1 else ''} this season")
    if zero_starters:
        specifics.append("Zero-point starters this week: " + ", ".join(x["name"] for x in zero_starters))
    if traded_away and 1 in [t["round"] for t in traded_away]:
        specifics.append(f"You do not own your {next_season} 1st — a full tank has less payoff")

    return {
        "league": {"name": league["name"], "id": league["league_id"], "format": f"{'Dynasty' if is_dynasty else 'Redraft'} · {scoring_type} · {len(rosters)} teams",
                   "starter_slots": starter_slots, "playoff_spots": ev["playoff_spots"], "regular_season_weeks": reg_end},
        "team": my_team_name, "week": week, "season": season,
        "record": f"{ev['wins']}-{ev['losses']}" + (f"-{ev['ties']}" if ev["ties"] else ""), "win_pct": ev["win_pct"],
        "rank": ev["rank"], "total_teams": ev["total_teams"], "in_playoffs": ev["in_playoffs"],
        "fpts": ev["fpts"], "fpa": ev["fpa"], "avg_age": ev["avg_age"], "pts_vs_avg": ev["pts_vs_avg"],
        "tier": ev["roster_tier"], "tier_color": ev["roster_tier_color"], "tier_icon": ev["roster_tier_icon"],
        "blended_tier": ev["tier"], "roster_composite": ev["roster_composite"], "composite": ev["composite"],
        "scores": ev["scores"], "strategy": ev["strategy"], "strat_color": ev["strat_color"], "strat_icon": ev["strat_icon"],
        "verdict": verdict, "specifics": specifics,
        "position_groups": position_groups, "needs": needs, "surplus": surplus,
        "lineup": {"current_pts": cur_pts, "optimal_pts": opt_pts, "gain": round(opt_pts - cur_pts, 1), "moves": moves,
                   "slots": [{"slot": x["slot"], "player": x["optimal"], "locked": x["locked"]} for x in lineup],
                   "zero_starters": zero_starters, "injured_starters": injured_starters},
        "season_log": log, "total_left_on_bench": total_left, "games_cost_by_lineup": games_cost, "avg_efficiency": avg_eff,
        "schedule": schedule, "exp_remaining_wins": exp_remaining_wins, "proj_final": f"{proj_final_wins}-{proj_final_losses}",
        "schedule_strength": sched_strength, "league_avg_strength": lg_avg_strength,
        "draft": {"season": next_season, "picks": picks, "traded_away": traded_away, "rounds": num_rounds},
        "sell_candidates": sell_candidates, "young_core": young_core,
        "roster": roster,
    }


# ── SEASON FORECAST ───────────────────────────────────────────────────────────

@router.post("/analysis/season-forecast")
async def get_season_forecast(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    baseline_week = current_week if current_week > 0 else 1

    proj_array = await get_projections(season, baseline_week)
    results = []

    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        playoff_week_start = league.get("settings", {}).get("playoff_week_start", 15)
        regular_season_end = playoff_week_start - 1
        playoff_spots = league.get("settings", {}).get("playoff_teams", 6)

        rosters, league_users = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_league_users(league["league_id"])
        )

        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue

        user_lookup = {u["user_id"]: u for u in league_users}

        def proj_score(roster):
            return sum(proj_map.get(str(pid), 0) for pid in (roster.get("starters") or []))

        my_proj = proj_score(my_roster)
        wins = my_roster.get("settings", {}).get("wins", 0)
        losses = my_roster.get("settings", {}).get("losses", 0)
        games_played = wins + losses
        weeks_remaining = max(0, regular_season_end - (current_week - 1))

        # Build proj scores for all teams
        all_proj_scores = [(r["roster_id"], proj_score(r)) for r in rosters]
        other_scores = [s for rid, s in all_proj_scores if rid != my_roster["roster_id"]]

        # Simulate remaining weeks — rotate through opponents
        proj_wins = wins
        proj_losses = losses
        import random
        random.seed(my_roster["roster_id"])  # deterministic per roster
        opponents = other_scores * ((weeks_remaining // max(len(other_scores), 1)) + 2)
        random.shuffle(opponents)
        for i in range(weeks_remaining):
            opp_score = opponents[i % len(opponents)] if opponents else my_proj
            if my_proj > opp_score:
                proj_wins += 1
            else:
                proj_losses += 1

        _mu = user_lookup.get(user_id)
        my_team_name = (_mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        results.append({
            "league": league["name"],
            "team": my_team_name,
            "current_record": f"{wins}-{losses}",
            "projected_record": f"{proj_wins}-{proj_losses}",
            "proj_wins": proj_wins,
            "proj_losses": proj_losses,
            "my_proj_score": round(my_proj, 1),
            "weeks_remaining": weeks_remaining,
            "in_playoffs": wins <= playoff_spots,
        })

    return {"results": results}

# ── DRAFT DATA ────────────────────────────────────────────────────────────────

@router.post("/analysis/draft-picks")
async def get_draft_picks(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    results = []

    for league in leagues:
        rosters, league_users, traded_picks, drafts = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_league_users(league["league_id"]),
            get_traded_picks(league["league_id"]),
            get_drafts(league["league_id"])
        )

        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue

        next_season = str(int(season) + 1)
        upcoming = []
        for pick in traded_picks:
            if pick.get("season") == next_season and pick.get("owner_id") == my_roster["roster_id"]:
                orig_roster = next((r for r in rosters if r["roster_id"] == pick.get("roster_id")), None)
                orig_user_id = orig_roster["owner_id"] if orig_roster else None
                orig_user = {u["user_id"]: u for u in league_users}.get(orig_user_id)
                orig_name = (orig_user or {}).get("display_name", f"Roster {pick.get('roster_id')}")
                upcoming.append({"round": pick["round"], "season": pick["season"], "original_owner": orig_name})

        _mu = next((u for u in league_users if u["user_id"] == user_id), None)
        my_team_name = (_mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        results.append({"league": league["name"], "team": my_team_name, "upcoming_picks": sorted(upcoming, key=lambda x: x["round"])})

    return {"results": results}

@router.post("/analysis/draft-dates")
async def get_draft_dates(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    results = []

    for league in leagues:
        drafts = await get_drafts(league["league_id"])
        for d in drafts:
            results.append({
                "league": league["name"],
                "draft_id": d.get("draft_id"),
                "status": d.get("status"),
                "type": d.get("type"),
                "start_time": d.get("start_time"),
                "season": d.get("season"),
            })

    return {"results": results}

@router.post("/analysis/live-draft")
async def get_live_draft(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    results = []

    for league in leagues:
        drafts = await get_drafts(league["league_id"])
        in_progress = [d for d in drafts if d.get("status") in ("drafting", "paused")]
        if not in_progress:
            continue

        rosters, league_users = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_league_users(league["league_id"])
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)

        for draft in in_progress:
            picks, draft_detail, traded = await asyncio.gather(
                get_draft_picks(draft["draft_id"]),
                get_draft(draft["draft_id"]),
                get_draft_traded_picks(draft["draft_id"])
            )

            num_teams = draft_detail.get("settings", {}).get("teams", len(rosters))
            slot_to_roster = draft_detail.get("slot_to_roster_id") or {}
            roster_to_user = {r["roster_id"]: r["owner_id"] for r in rosters}
            user_lookup = {u["user_id"]: u for u in league_users}

            traded_map = {f"{p['round']}-{p['roster_id']}": p["owner_id"] for p in traded if p.get("season") == draft_detail.get("season")}
            is_snake = draft_detail.get("type") == "snake"

            def get_pick_owner(pick_num):
                round_idx = (pick_num - 1) // num_teams
                rnd = round_idx + 1
                pos = ((pick_num - 1) % num_teams) + 1
                slot = (num_teams - pos + 1) if (is_snake and round_idx % 2 == 1) else pos
                orig_roster = slot_to_roster.get(str(slot)) or slot_to_roster.get(slot)
                if orig_roster:
                    key = f"{rnd}-{orig_roster}"
                    current = traded_map.get(key, orig_roster)
                    uid = roster_to_user.get(current)
                    return user_lookup.get(uid, {}).get("display_name", f"Roster {current}")
                return "Unknown"

            picks_made = len(picks)
            current_pick = picks_made + 1
            my_next_picks = []
            for pick_num in range(current_pick, num_teams * draft_detail.get("settings", {}).get("rounds", 4) + 1):
                owner = get_pick_owner(pick_num)
                uid = next((u["user_id"] for u in league_users if u.get("display_name") == owner), None)
                if uid == user_id:
                    my_next_picks.append(pick_num)
                    if len(my_next_picks) >= 3:
                        break

            recent = picks[-5:] if picks else []
            for p in recent:
                pid = p.get("player_id")
                pl = players_db.get(str(pid)) if pid else None
                p["player_name"] = player_name(pl) if pl else str(pid)
                p["position"] = (pl or {}).get("position", "")

            _mu = user_lookup.get(user_id)
            results.append({
                "league": league["name"],
                "team": (_mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", ""),
                "draft_id": draft["draft_id"],
                "status": draft.get("status"),
                "current_pick": current_pick,
                "picks_on_clock": get_pick_owner(current_pick),
                "my_next_picks": my_next_picks,
                "recent_picks": list(reversed(recent)),
            })

    return {"results": results}

# ── STARTER UPGRADES ──────────────────────────────────────────────────────────

@router.post("/analysis/starter-upgrades")
async def get_starter_upgrades(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week
    MIN_GAIN = 1.5
    RELEVANT = {"QB", "RB", "WR", "TE", "K", "DEF"}

    proj_array, stats_array = await asyncio.gather(get_projections(season, week), get_stats(season, week))
    stats_map = build_stats_map(stats_array)
    has_played = lambda pid: stats_map.get(str(pid), {}).get("gp", 0) >= 1

    results = []
    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        starter_slots = [s for s in league.get("roster_positions", []) if s not in ("BN", "IR", "TAXI")]

        rosters, league_users, matchups = await asyncio.gather(
            get_rosters(league["league_id"]), get_league_users(league["league_id"]), get_matchups(league["league_id"], week)
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        my_user = next((u for u in league_users if u["user_id"] == user_id), None)
        my_team_name = (my_user or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")

        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        starters_ordered = [str(s) for s in ((my_matchup or my_roster).get("starters") or [])]
        starter_set = set(starters_ordered)
        taxi_ids = set(str(t) for t in (my_roster.get("taxi") or []))
        rostered = {str(pid) for r in rosters for pid in (r.get("players") or [])}

        def enrich(pid, is_fa=False):
            p = players_db.get(str(pid))
            if not p or p.get("position") not in RELEVANT:
                return None
            return {"id": str(pid), "name": player_name(p), "position": p["position"], "team": p.get("team", "FA"),
                    "pts": proj_map.get(str(pid), 0), "injury_status": p.get("injury_status"), "is_fa": is_fa}

        # Unplayed bench players only (played bench can't be started)
        bench = [e for pid in (my_roster.get("players") or [])
                 if str(pid) not in starter_set and str(pid) not in taxi_ids and not has_played(pid)
                 if (e := enrich(pid))]

        # Unplayed FAs with a meaningful projection
        fas = sorted(
            [e for pid, p in players_db.items()
             if pid not in rostered and p.get("position") in RELEVANT
             and proj_map.get(pid, 0) >= 3 and not has_played(pid)
             if (e := enrich(pid, is_fa=True))],
            key=lambda x: -x["pts"]
        )[:150]

        # Roster pool = current starters + unplayed bench (played starters lock inside compute_lineup)
        roster_pool = [e for pid in starters_ordered if pid and pid != "0" if (e := enrich(pid))] + bench
        lineup = compute_lineup(starter_slots, starters_ordered, roster_pool, has_played, key="pts")
        moves, _ = lineup_moves(lineup)
        locked = sum(1 for x in lineup if x["locked"])

        moved_ids = {m["player"]["id"] for m in moves if m["type"] == "move"}
        upgrades = []
        for x in lineup:
            if x["locked"]:
                continue
            cur, opt = x["current"], x["optimal"]
            elig = SLOT_ELIGIBILITY.get(x["slot"], [x["slot"]])
            base_pts = max((cur or {}).get("pts", 0), (opt or {}).get("pts", 0))
            floor = base_pts + MIN_GAIN
            roster_up = [opt] if opt and (cur is None or opt["id"] != cur["id"]) else []
            # An independent bench<->starter swap must clear MIN_GAIN; coupled slot moves always show
            if roster_up and cur and opt["id"] not in moved_ids and cur["id"] not in moved_ids \
                    and (opt["pts"] - cur["pts"]) < MIN_GAIN:
                roster_up = []
                base_pts = cur["pts"]; floor = base_pts + MIN_GAIN
            fa_ups = [f for f in fas if f["position"] in elig and f["pts"] > floor][:2]
            zero_proj = cur is not None and (cur.get("pts") or 0) <= 0
            if roster_up or fa_ups or (zero_proj and cur):
                upgrades.append({
                    "slot": x["slot"], "current_starter": cur, "zero_projection": zero_proj,
                    "bench_upgrades": roster_up, "fa_upgrades": fa_ups,
                })

        results.append({
            "league": league["name"], "team": my_team_name, "upgrades": upgrades, "moves": moves,
            "starter_count": len(starters_ordered), "locked_count": locked, "optimal": len(upgrades) == 0,
        })

    results.sort(key=lambda r: -len(r["upgrades"]))
    return {"week": week, "results": results}

# ── BENCH VS FA ───────────────────────────────────────────────────────────────

@router.post("/analysis/bench-vs-fa")
async def get_bench_vs_fa(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week

    proj_array = await get_projections(season, week)
    results = []

    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)

        rosters, league_users, matchups = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_league_users(league["league_id"]),
            get_matchups(league["league_id"], week)
        )

        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue

        user_lookup = {u["user_id"]: u for u in league_users}
        my_user = user_lookup.get(user_id)
        my_team_name = (my_user or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")

        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        starter_ids = set(str(pid) for pid in ((my_matchup or my_roster).get("starters") or []))
        taxi_ids = set(str(pid) for pid in (my_roster.get("taxi") or []))

        # All rostered players
        rostered_ids = set()
        for r in rosters:
            for pid in (r.get("players") or []):
                rostered_ids.add(str(pid))

        RELEVANT_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}

        my_bench = []
        for pid in (my_roster.get("players") or []):
            if str(pid) in starter_ids or str(pid) in taxi_ids:
                continue
            p = players_db.get(str(pid))
            if not p or p.get("position") not in RELEVANT_POSITIONS:
                continue
            my_bench.append({
                "id": str(pid),
                "name": player_name(p),
                "position": p.get("position"),
                "team": p.get("team", ""),
                "pts": proj_map.get(str(pid), 0),
                "injury_status": p.get("injury_status"),
            })
        my_bench.sort(key=lambda x: x["pts"])  # weakest first

        # Top FAs by position
        fa_by_pos = {}
        for pid, p in players_db.items():
            if str(pid) in rostered_ids:
                continue
            pos = p.get("position", "")
            if pos not in RELEVANT_POSITIONS:
                continue
            pts = proj_map.get(str(pid), 0)
            if pts < 3:
                continue
            if pos not in fa_by_pos:
                fa_by_pos[pos] = []
            fa_by_pos[pos].append({
                "id": str(pid),
                "name": player_name(p),
                "position": pos,
                "team": p.get("team", ""),
                "pts": pts,
                "injury_status": p.get("injury_status"),
            })

        for pos in fa_by_pos:
            fa_by_pos[pos].sort(key=lambda x: -x["pts"])

        # Find drops: bench players worse than available FAs at same position
        # Each FA can only be recommended once (deduplicate)
        drops = []
        MIN_GAIN = 2.0
        used_fas = set()
        for bench_p in sorted(my_bench, key=lambda x: x["pts"]):  # weakest bench first
            pos = bench_p["position"]
            # Find best unused FA at this position
            best_fa = next((fa for fa in (fa_by_pos.get(pos) or [])
                           if fa["id"] not in used_fas
                           and fa["pts"] > bench_p["pts"] + MIN_GAIN), None)
            if not best_fa:
                continue
            used_fas.add(best_fa["id"])
            drops.append({
                "drop": bench_p,
                "add": best_fa,
                "gain": round(best_fa["pts"] - bench_p["pts"], 1),
            })

        drops.sort(key=lambda x: -x["gain"])

        results.append({
            "league": league["name"],
            "team": my_team_name,
            "drops": drops,
            "bench": my_bench,
            "optimal": len(drops) == 0,
        })

    results.sort(key=lambda r: -len(r["drops"]))
    return {"week": week, "results": results}


# ── WEEK REVIEW ───────────────────────────────────────────────────────────────

@router.post("/analysis/week-review")
async def get_week_review(req: WeekRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week
    next_week = week + 1
    UNDER_PCT, UNDER_MIN_PROJ, UNDER_MIN_DIFF = 0.60, 8.0, 5.0

    proj_array, next_proj_array, stats_array = await asyncio.gather(
        get_projections(season, week), get_projections(season, next_week), get_stats(season, week)
    )
    stats_map = build_stats_map(stats_array)
    never_played = lambda pid: False          # hindsight: everyone is fair game
    week_done = week < current_week

    results = []
    for league in leagues:
        if league.get("status") == "complete":
            continue
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        next_proj_map = build_proj_map(next_proj_array, ss)
        starter_slots = [s for s in league.get("roster_positions", []) if s not in ("BN", "IR", "TAXI")]

        rosters, league_users, matchups, next_matchups = await asyncio.gather(
            get_rosters(league["league_id"]), get_league_users(league["league_id"]),
            get_matchups(league["league_id"], week), get_matchups(league["league_id"], next_week),
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        if not my_matchup:
            continue
        opp_matchup = next((m for m in matchups if m["matchup_id"] == my_matchup["matchup_id"]
                            and m["roster_id"] != my_roster["roster_id"]), None)

        user_lookup = {u["user_id"]: u for u in league_users}
        roster_lookup = {r["roster_id"]: r for r in rosters}
        my_user = user_lookup.get(user_id)
        my_team_name = (my_user or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        opp_user = user_lookup.get((roster_lookup.get(opp_matchup["roster_id"]) or {}).get("owner_id")) if opp_matchup else None
        opp_name = (opp_user or {}).get("metadata", {}).get("team_name") or (opp_user or {}).get("display_name", "Opponent")

        actual = my_matchup.get("players_points") or {}
        starters_ordered = [str(s) for s in (my_matchup.get("starters") or [])]
        starter_set = set(starters_ordered)
        taxi_ids = set(str(t) for t in (my_roster.get("taxi") or []))

        # ── Pool with actual + projected for the reviewed week ──
        pool = []
        for pid in (my_roster.get("players") or []):
            pid = str(pid)
            if pid in taxi_ids:
                continue
            p = players_db.get(pid)
            if not p:
                continue
            pool.append({
                "id": pid, "name": player_name(p), "position": p.get("position", "UNK"), "team": p.get("team", "FA"),
                "pts": round(actual.get(pid, 0), 2), "proj": proj_map.get(pid, 0),
                "played": stats_map.get(pid, {}).get("gp", 0) >= 1,
                "is_starter": pid in starter_set, "injury_status": p.get("injury_status"),
            })
        by_id = {p["id"]: p for p in pool}

        my_pts = round(my_matchup.get("points", 0), 2)
        opp_pts = round(opp_matchup.get("points", 0), 2) if opp_matchup else None
        won = (my_pts > opp_pts) if opp_pts is not None else None

        # ── Hindsight optimal ──
        hind = compute_lineup(starter_slots, starters_ordered, pool, never_played, key="pts")
        optimal_pts = round(sum((s["optimal"] or {}).get("pts", 0) for s in hind), 2)
        starter_pts = round(sum((s["current"] or {}).get("pts", 0) for s in hind), 2)
        left_on_bench = round(optimal_pts - starter_pts, 2)
        efficiency = round(starter_pts / optimal_pts * 100, 1) if optimal_pts > 0 else 100.0
        grade = "A" if efficiency >= 97 else "B" if efficiency >= 90 else "C" if efficiency >= 80 else "D" if efficiency >= 70 else "F"
        missed_moves, missed = lineup_moves(hind)
        cost_the_game = bool(won is False and opp_pts is not None and optimal_pts > opp_pts)

        # ── Under / over achievers among starters ──
        under, over = [], []
        for pid in starters_ordered:
            p = by_id.get(pid)
            if not p or not p["played"]:
                continue
            diff = round(p["pts"] - p["proj"], 1)
            if p["proj"] >= UNDER_MIN_PROJ and (p["pts"] < p["proj"] * UNDER_PCT or diff <= -UNDER_MIN_DIFF):
                under.append({**p, "diff": diff})
            elif diff >= UNDER_MIN_DIFF:
                over.append({**p, "diff": diff})
        under.sort(key=lambda x: x["diff"]); over.sort(key=lambda x: -x["diff"])

        # ── Next week recs ──
        nxt_matchup = next((m for m in next_matchups if m["roster_id"] == my_roster["roster_id"]), None)
        nxt_starters = [str(s) for s in ((nxt_matchup or my_roster).get("starters") or [])]
        nxt_set = set(nxt_starters)
        nxt_pool = []
        for p in pool:
            pl = players_db.get(p["id"]) or {}
            bye = pl.get("bye_week")
            nxt_pool.append({**p, "pts": next_proj_map.get(p["id"], 0), "is_starter": p["id"] in nxt_set,
                             "on_bye": bool(bye and int(bye) == next_week)})
        nxt = compute_lineup(starter_slots, nxt_starters, nxt_pool, never_played, key="pts")
        next_moves, next_swaps = lineup_moves(nxt)
        next_cur = round(sum((s["current"] or {}).get("pts", 0) for s in nxt), 1)
        next_opt = round(sum((s["optimal"] or {}).get("pts", 0) for s in nxt), 1)
        next_flags = [p for p in nxt_pool if p["is_starter"] and (p["on_bye"] or
                      (p.get("injury_status") or "").lower() in ("out", "ir", "pup", "sus", "doubtful"))]
        under_ids = {u["id"] for u in under}
        still_starting_under = [p for p in nxt_pool if p["is_starter"] and p["id"] in under_ids]

        results.append({
            "league": league["name"], "team": my_team_name, "opp_name": opp_name,
            "won": won, "my_pts": my_pts, "opp_pts": opp_pts,
            "optimal_pts": optimal_pts, "starter_pts": starter_pts, "left_on_bench": left_on_bench,
            "efficiency": efficiency, "grade": grade, "cost_the_game": cost_the_game,
            "missed_swaps": missed, "missed_moves": missed_moves, "underachievers": under, "overachievers": over[:3],
            "next_week": next_week, "next_swaps": next_swaps, "next_moves": next_moves, "next_current_pts": next_cur,
            "next_optimal_pts": next_opt, "next_flags": next_flags, "still_starting_under": still_starting_under,
        })

    grade_order = {"F": 0, "D": 1, "C": 2, "B": 3, "A": 4}
    results.sort(key=lambda r: (grade_order.get(r["grade"], 9), -r["left_on_bench"]))
    summary = {
        "wins": sum(1 for r in results if r["won"] is True),
        "losses": sum(1 for r in results if r["won"] is False),
        "total_left_on_bench": round(sum(r["left_on_bench"] for r in results), 1),
        "cost_games": sum(1 for r in results if r["cost_the_game"]),
        "avg_efficiency": round(sum(r["efficiency"] for r in results) / len(results), 1) if results else 0,
        "grades": {g: sum(1 for r in results if r["grade"] == g) for g in "ABCDF"},
    }
    return {"week": week, "week_done": week_done, "summary": summary, "results": results}
