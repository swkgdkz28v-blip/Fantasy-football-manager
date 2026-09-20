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
        rosters, matchups = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_matchups(league["league_id"], week)
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
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
            results.append({"league": league["name"], "injured": injured})

    return {"results": results}

@router.post("/alerts/questionable-starters")
async def get_questionable_starters(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    week = req.week or current_week
    user_id = user["user_id"]
    results = []

    for league in leagues:
        rosters, matchups = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_matchups(league["league_id"], week)
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
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
            results.append({"league": league["name"], "questionable": questionable})

    return {"results": results}

@router.post("/alerts/starters-on-bye")
async def get_starters_on_bye(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    week = req.week or current_week
    user_id = user["user_id"]
    results = []

    for league in leagues:
        rosters, matchups = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_matchups(league["league_id"], week)
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
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
            results.append({"league": league["name"], "on_bye": on_bye})

    return {"results": results}

@router.post("/alerts/open-starter-spots")
async def get_open_starter_spots(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    week = req.week or current_week
    user_id = user["user_id"]
    results = []

    for league in leagues:
        rosters, matchups = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_matchups(league["league_id"], week)
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        starters = my_matchup.get("starters", []) if my_matchup else my_roster.get("starters", [])
        open_spots = [i for i, pid in enumerate(starters) if not pid or pid == "0"]
        if open_spots:
            results.append({"league": league["name"], "open_slots": len(open_spots)})

    return {"results": results}

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

        results.append({
            "league": league["name"],
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

        results.append({
            "league": league["name"],
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
                skipped.append({"league": league["name"], "my_live": my_live, "opp_live": opp_live, "my_max": my_max, "opp_max": opp_max})
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

        results.append({
            "league": league["name"],
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

# ── OPTIMAL LINEUP ────────────────────────────────────────────────────────────

@router.post("/analysis/optimal-lineup")
async def get_optimal_lineup(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week

    proj_array = await get_projections(season, week)
    results = []
    optimal_leagues = []

    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        roster_positions = league.get("roster_positions", [])
        starter_slots = [s for s in roster_positions if s not in ("BN", "IR", "TAXI")]

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
        week_starters = set(my_matchup.get("starters", []) if my_matchup else my_roster.get("starters", []))

        taxi_ids = set(my_roster.get("taxi") or [])
        pool = []
        for pid in (my_roster.get("players") or []):
            if str(pid) in taxi_ids:
                continue
            p = players_db.get(str(pid))
            if not p:
                continue
            pool.append({
                "id": str(pid),
                "name": player_name(p),
                "position": p.get("position", "UNK"),
                "team": p.get("team", "FA"),
                "pts": proj_map.get(str(pid), 0),
                "injury_status": p.get("injury_status"),
                "is_starter": str(pid) in week_starters,
            })
        pool.sort(key=lambda x: -x["pts"])

        slots_sorted = sorted(starter_slots, key=lambda s: len(SLOT_ELIGIBILITY.get(s, [s])))
        assigned = set()
        optimal_slots = []
        for slot in slots_sorted:
            eligible = SLOT_ELIGIBILITY.get(slot, [slot])
            best = next((p for p in pool if p["position"] in eligible and p["id"] not in assigned), None)
            if best:
                assigned.add(best["id"])
                optimal_slots.append({"slot": slot, "player": best})
            else:
                optimal_slots.append({"slot": slot, "player": None})

        slot_queue = {}
        for os in optimal_slots:
            slot_queue.setdefault(os["slot"], []).append(os)
        used_slots = {}
        optimal_in_order = []
        for slot in starter_slots:
            idx = used_slots.get(slot, 0)
            matches = [os for os in optimal_slots if os["slot"] == slot]
            optimal_in_order.append(matches[idx] if idx < len(matches) else {"slot": slot, "player": None})
            used_slots[slot] = idx + 1

        optimal_pts = round(sum((os["player"]["pts"] if os["player"] else 0) for os in optimal_in_order), 2)
        current_pts = round(sum(proj_map.get(pid, 0) for pid in week_starters), 2)
        gain = round(optimal_pts - current_pts, 2)
        bench = [p for p in pool if p["id"] not in assigned]

        if gain <= 0:
            optimal_leagues.append({"league": league["name"], "team": my_team_name, "pts": optimal_pts})
        else:
            results.append({
                "league": league["name"],
                "team": my_team_name,
                "optimal_pts": optimal_pts,
                "current_pts": current_pts,
                "gain": gain,
                "lineup": optimal_in_order,
                "bench": bench,
            })

    return {"week": week, "results": results, "optimal_leagues": optimal_leagues}

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
            is_flex_eligible = any(pos in fs["eligible"] for fs in flex_slots_list)
            if dedicated == 0 and not is_flex_eligible:
                continue

            owned = len(players_by_pos[pos])
            pos_flex = sum(1 for fs in flex_slots_list if pos in fs["eligible"])

            if pos == "QB":
                min_needed = qb_demand + 2
            elif pos in ("RB", "WR"):
                min_needed = dedicated + pos_flex + 1
            elif pos == "TE":
                min_needed = dedicated + 1
            else:
                min_needed = dedicated

            if owned >= min_needed:
                continue

            shortage = dedicated - owned
            if owned == 0 and dedicated > 0:
                grade = "Empty"
            elif shortage > 0:
                grade = "Underfilled"
            elif owned < dedicated + 1:
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
    weeks_completed = min(week - 1, current_week - 1)

    proj_array = await get_projections(season, week)

    ytd_stats_map = {}
    if weeks_completed > 0:
        week_stats_list = await asyncio.gather(*[get_stats(season, w) for w in range(1, weeks_completed + 1)])
        for week_data in week_stats_list:
            sm = build_stats_map(week_data)
            for pid, stats in sm.items():
                if pid not in ytd_stats_map:
                    ytd_stats_map[pid] = {}
                for stat, val in stats.items():
                    ytd_stats_map[pid][stat] = ytd_stats_map[pid].get(stat, 0) + val

    results = []
    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        roster_positions = league.get("roster_positions", [])
        starter_slots = [s for s in roster_positions if s not in ("BN", "IR", "TAXI")]

        def score_player(pid):
            week_pts = proj_map.get(str(pid), 0)
            ytd_avg = 0
            raw = ytd_stats_map.get(str(pid))
            if raw and weeks_completed > 0:
                ytd_pts = sum(ss.get(stat, 0) * val for stat, val in raw.items())
                gp = raw.get("gp", weeks_completed)
                ytd_avg = ytd_pts / max(gp, 1)
            blended = (week_pts * 0.6 + ytd_avg * 0.4) if weeks_completed > 0 else week_pts
            return round(week_pts, 1), round(ytd_avg, 1), round(blended, 1)

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
        week_starters = set(str(pid) for pid in (my_matchup.get("starters", []) if my_matchup else my_roster.get("starters", [])))
        taxi_ids = set(str(pid) for pid in (my_roster.get("taxi") or []))

        pool = []
        for pid in my_roster.get("players", []):
            if str(pid) in taxi_ids:
                continue
            p = players_db.get(str(pid))
            if not p:
                continue
            wp, ya, bl = score_player(pid)
            pool.append({"id": str(pid), "name": player_name(p), "position": p.get("position", "UNK"), "team": p.get("team", ""), "week_pts": wp, "ytd_avg": ya, "blended": bl, "is_starter": str(pid) in week_starters})
        pool.sort(key=lambda x: -x["blended"])

        slots_sorted = sorted(starter_slots, key=lambda s: len(SLOT_ELIGIBILITY.get(s, [s])))
        assigned = set()
        optimal = []
        for slot in slots_sorted:
            eligible = SLOT_ELIGIBILITY.get(slot, [slot])
            best = next((p for p in pool if p["position"] in eligible and p["id"] not in assigned), None)
            if best:
                assigned.add(best["id"])
                optimal.append({"slot": slot, "player": best})

        starters = [p for p in pool if p["is_starter"]]
        current_pts = round(sum(p["blended"] for p in starters), 1)
        optimal_pts = round(sum(o["player"]["blended"] for o in optimal), 1)
        gain = round(optimal_pts - current_pts, 1)

        should_start = [o["player"] for o in optimal if not o["player"]["is_starter"]]
        should_bench = [p for p in starters if p["id"] not in assigned]
        bench = [p for p in pool if p["id"] not in assigned]

        results.append({
            "league": league["name"],
            "team": my_team_name,
            "optimal_pts": optimal_pts,
            "current_pts": current_pts,
            "gain": gain,
            "should_start": should_start,
            "should_bench": should_bench,
            "lineup": optimal,
            "bench": bench[:8],
        })

    return {"week": week, "results": results}

# ── OVERVIEW (Contender + Strategy) ───────────────────────────────────────────

@router.post("/analysis/overview")
async def get_overview(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week

    proj_array = await get_projections(season, week)
    results = []

    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        roster_positions = league.get("roster_positions", [])
        num_rounds = league.get("settings", {}).get("draft_rounds", 4)
        playoff_spots = league.get("settings", {}).get("playoff_teams", 6)
        playoff_week_start = league.get("settings", {}).get("playoff_week_start", 15)
        regular_season_weeks = playoff_week_start - 1

        rosters, league_users, traded_picks = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_league_users(league["league_id"]),
            get_traded_picks(league["league_id"])
        )

        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue

        user_lookup = {u["user_id"]: u for u in league_users}
        my_user = user_lookup.get(user_id)
        my_team_name = (my_user or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")

        wins = my_roster.get("settings", {}).get("wins", 0)
        losses = my_roster.get("settings", {}).get("losses", 0)
        ties = my_roster.get("settings", {}).get("ties", 0)
        games_played = wins + losses + ties
        win_pct = wins / games_played if games_played > 0 else 0

        sorted_rosters = sorted(rosters, key=lambda r: (-(r.get("settings") or {}).get("wins", 0), -(r.get("settings") or {}).get("fpts", 0)))
        rank = next((i + 1 for i, r in enumerate(sorted_rosters) if r["roster_id"] == my_roster["roster_id"]), len(rosters))
        rank_pct = rank / len(rosters)
        in_playoffs = rank <= playoff_spots
        total_games_played = sum((r.get("settings") or {}).get("wins", 0) + (r.get("settings") or {}).get("losses", 0) for r in rosters)
        season_started = total_games_played > 0 or current_week > 1

        # Roster score
        starter_ids = set(str(pid) for pid in (my_roster.get("starters") or []))
        taxi_ids = set(str(pid) for pid in (my_roster.get("taxi") or []))
        my_starters = [{"id": str(pid), "position": (players_db.get(str(pid)) or {}).get("position", ""), "age": (players_db.get(str(pid)) or {}).get("age"), "pts": proj_map.get(str(pid), 0)} for pid in (my_roster.get("players") or []) if str(pid) in starter_ids]
        my_bench = [{"pts": proj_map.get(str(pid), 0)} for pid in (my_roster.get("players") or []) if str(pid) not in starter_ids and str(pid) not in taxi_ids]

        league_avg = sum(sum(proj_map.get(str(pid), 0) for pid in (r.get("starters") or [])) for r in rosters) / len(rosters) if rosters else 0
        my_starter_pts = sum(p["pts"] for p in my_starters)
        pts_vs_avg = my_starter_pts / league_avg if league_avg > 0 else 1
        roster_score = 5 if pts_vs_avg >= 1.15 else 4 if pts_vs_avg >= 1.05 else 3 if pts_vs_avg >= 0.95 else 2 if pts_vs_avg >= 0.85 else 1

        # Age score
        starter_ages = [p["age"] for p in my_starters if p.get("age")]
        avg_age = sum(starter_ages) / len(starter_ages) if starter_ages else 26
        age_score = 5 if 25 <= avg_age <= 28 else 4 if avg_age <= 30 else 3 if avg_age >= 23 else 2

        # Draft capital
        next_season = str(int(season) + 1)
        picks_next = [p for p in traded_picks if p.get("season") == next_season]
        t_map = {f"{p['round']}-{p['roster_id']}": p["owner_id"] for p in picks_next}
        baseline_cap = sum(round_weight(r) for r in range(1, num_rounds + 1))
        my_cap = 0
        missing_rounds = []
        for rnd in range(1, num_rounds + 1):
            owned_count = sum(1 for r in rosters if t_map.get(f"{rnd}-{r['roster_id']}", r["roster_id"]) == my_roster["roster_id"])
            my_key = f"{rnd}-{my_roster['roster_id']}"
            if t_map.get(my_key, my_roster["roster_id"]) != my_roster["roster_id"]:
                missing_rounds.append(rnd)
            my_cap += owned_count * round_weight(rnd)
        cap_ratio = my_cap / baseline_cap if baseline_cap > 0 else 1
        draft_score = 5 if cap_ratio >= 1.8 else 4 if cap_ratio >= 1.4 else 3 if cap_ratio >= 0.9 else 2 if cap_ratio >= 0.5 else 1
        if 1 in missing_rounds:
            draft_score = min(draft_score, 2)
        if 1 in missing_rounds and 2 in missing_rounds:
            draft_score = 1

        # Depth score
        depth_count = sum(1 for p in my_bench if p["pts"] >= 5)
        depth_score = 5 if depth_count >= 6 else 4 if depth_count >= 4 else 3 if depth_count >= 2 else 2 if depth_count >= 1 else 1

        # Record score
        record_score = 3
        if season_started and games_played > 0:
            wp_score = 5 if win_pct >= 0.70 else 4 if win_pct >= 0.55 else 3 if win_pct >= 0.45 else 2 if win_pct >= 0.30 else 1
            rank_score = 5 if rank_pct <= 0.20 else 4 if rank_pct <= 0.40 else 3 if rank_pct <= 0.60 else 2 if rank_pct <= 0.80 else 1
            sp = games_played / regular_season_weeks
            record_score = max(1, min(5, round(wp_score * (1 - sp * 0.4) + rank_score * (sp * 0.4 + 0.3))))

        # Composite
        if season_started and games_played > 0:
            sp = min(games_played / regular_season_weeks, 1)
            rec_w = 0.20 * sp
            composite = roster_score * (0.75 - rec_w * 0.5) + record_score * rec_w + draft_score * (0.15 - rec_w * 0.3) + age_score * 0.05 + depth_score * 0.05
        else:
            composite = roster_score * 0.75 + draft_score * 0.15 + age_score * 0.05 + depth_score * 0.05

        # Tier
        if composite > 4.0:
            tier, tier_color, tier_icon = "Juggernaut", "#00e5a0", "👑"
        elif composite > 3.0:
            tier, tier_color, tier_icon = "Contender", "#5c9eff", "🏆"
        elif composite > 2.0:
            tier, tier_color, tier_icon = "Fringe", "#ffb347", "⚡"
        else:
            tier, tier_color, tier_icon = "Rebuild", "#ff5c5c", "🔨"

        # Strategy
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

        scores = {"Roster": roster_score, "Draft": draft_score, "Age": age_score, "Depth": depth_score, "Record": record_score}
        results.append({
            "league": league["name"],
            "team": my_team_name,
            "record": f"{wins}-{losses}" + (f"-{ties}" if ties else ""),
            "rank": rank,
            "total_teams": len(rosters),
            "in_playoffs": in_playoffs,
            "composite": round(composite, 2),
            "tier": tier,
            "tier_color": tier_color,
            "tier_icon": tier_icon,
            "strategy": strategy,
            "strat_color": strat_color,
            "strat_icon": strat_icon,
            "strat_actions": strat_actions,
            "scores": scores,
            "avg_age": round(avg_age, 1),
            "starter_pts": round(my_starter_pts, 1),
            "pts_vs_avg": round(pts_vs_avg, 3),
        })

    results.sort(key=lambda r: {"Win Now": 0, "Sell High": 1, "Patience": 2, "Trust the Process": 3, "Full Rebuild": 4}.get(r["strategy"], 9))
    return {"results": results}

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

        proj_wins = wins
        proj_losses = losses
        for _ in range(weeks_remaining):
            opp_proj = sum(proj_score(r) for r in rosters if r["owner_id"] != user_id) / max(len(rosters) - 1, 1)
            if my_proj > opp_proj:
                proj_wins += 1
            else:
                proj_losses += 1

        results.append({
            "league": league["name"],
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

        results.append({"league": league["name"], "upcoming_picks": sorted(upcoming, key=lambda x: x["round"])})

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

            results.append({
                "league": league["name"],
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

    proj_array = await get_projections(season, week)
    results = []

    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        roster_positions = league.get("roster_positions", [])
        starter_slots = [s for s in roster_positions if s not in ("BN", "IR", "TAXI")]

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
        starter_ids = set(str(pid) for pid in (my_matchup.get("starters", []) if my_matchup else my_roster.get("starters", [])))
        taxi_ids = set(str(pid) for pid in (my_roster.get("taxi") or []))

        # All rostered players across league (to find FAs)
        rostered_ids = set()
        for r in rosters:
            for pid in (r.get("players") or []):
                rostered_ids.add(str(pid))

        def enrich(pid, is_starter=False, is_fa=False):
            p = players_db.get(str(pid))
            if not p:
                return None
            pos = p.get("position", "UNK")
            if pos not in ("QB", "RB", "WR", "TE", "K", "DEF"):
                return None
            return {
                "id": str(pid),
                "name": player_name(p),
                "position": pos,
                "team": p.get("team", "FA"),
                "pts": proj_map.get(str(pid), 0),
                "injury_status": p.get("injury_status"),
                "is_starter": is_starter,
                "is_fa": is_fa,
            }

        my_starters_list = [p for pid in starter_ids if (p := enrich(pid, is_starter=True)) is not None]
        my_bench = [p for pid in (my_roster.get("players") or [])
                    if str(pid) not in starter_ids and str(pid) not in taxi_ids
                    if (p := enrich(pid)) is not None]

        # Match starters to slots using greedy assignment (dedicated slots first)
        # This mirrors how Sleeper assigns players to slots
        slots_sorted = sorted(starter_slots, key=lambda s: len(SLOT_ELIGIBILITY.get(s, [s])))
        assigned_starter_ids = set()
        slot_to_starter = {}  # slot_index → player
        for i, slot in enumerate(slots_sorted):
            eligible = SLOT_ELIGIBILITY.get(slot, [slot])
            match = next((p for p in my_starters_list
                         if p["position"] in eligible and p["id"] not in assigned_starter_ids), None)
            if match:
                assigned_starter_ids.add(match["id"])
                slot_to_starter[i] = match

        # Find eligible FAs: in players_db, not rostered, relevant positions
        RELEVANT_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}
        fa_candidates = []
        for pid, p in players_db.items():
            if str(pid) in rostered_ids:
                continue
            pos = p.get("position", "")
            if pos not in RELEVANT_POSITIONS:
                continue
            pts = proj_map.get(str(pid), 0)
            if pts < 3:  # skip low-value FAs
                continue
            fa_candidates.append({
                "id": str(pid),
                "name": player_name(p),
                "position": pos,
                "team": p.get("team", "FA"),
                "pts": pts,
                "injury_status": p.get("injury_status"),
                "is_fa": True,
            })
        fa_candidates.sort(key=lambda x: -x["pts"])
        top_fas = fa_candidates[:100]  # limit for performance

        # Find upgrades per starter slot — track flagged starters to avoid repeats
        upgrades = []
        flagged_starters = set()  # starter ids already flagged for replacement

        for i, slot in enumerate(slots_sorted):
            eligible = SLOT_ELIGIBILITY.get(slot, [slot])
            slot_starter = slot_to_starter.get(i)
            if not slot_starter or slot_starter["id"] in flagged_starters:
                continue

            starter_pts = slot_starter["pts"]
            MIN_GAIN = 1.5

            # Check bench upgrades
            bench_ups = [p for p in my_bench
                        if p["position"] in eligible
                        and p["pts"] > starter_pts + MIN_GAIN]
            bench_ups.sort(key=lambda x: -x["pts"])
            bench_ups = bench_ups[:2]

            # Check FA upgrades
            fa_ups = [p for p in top_fas
                     if p["position"] in eligible
                     and p["pts"] > starter_pts + MIN_GAIN]
            fa_ups.sort(key=lambda x: -x["pts"])
            fa_ups = fa_ups[:2]

            if bench_ups or fa_ups:
                flagged_starters.add(slot_starter["id"])
                upgrades.append({
                    "slot": slot,
                    "current_starter": slot_starter,
                    "bench_upgrades": bench_ups,
                    "fa_upgrades": fa_ups,
                })

        results.append({
            "league": league["name"],
            "team": my_team_name,
            "upgrades": upgrades,
            "starter_count": len(my_starters_list),
            "optimal": len(upgrades) == 0,
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

        starter_ids = set(str(pid) for pid in (my_roster.get("starters") or []))
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
        drops = []
        MIN_GAIN = 2.0
        for bench_p in my_bench:
            pos = bench_p["position"]
            best_fa = (fa_by_pos.get(pos) or [None])[0]
            if not best_fa:
                continue
            if best_fa["pts"] > bench_p["pts"] + MIN_GAIN:
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

# ── CLAUDE TRADE ADVICE ───────────────────────────────────────────────────────

@router.post("/analysis/claude-trade-advice")
async def get_claude_trade_advice(req: UserRequest):
    import os
    try:
        import anthropic as anthropic_sdk
    except ImportError:
        raise HTTPException(status_code=500, detail="Anthropic SDK not installed")

    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week

    proj_array = await get_projections(season, week)

    league_summaries = []

    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        roster_positions = league.get("roster_positions", [])
        starter_slots = [s for s in roster_positions if s not in ("BN", "IR", "TAXI")]
        is_dynasty = league.get("settings", {}).get("type", 0) == 2
        scoring_type = "PPR" if ss.get("rec", 0) >= 1 else "Half PPR" if ss.get("rec", 0) >= 0.5 else "Standard"
        sf_count = sum(1 for s in starter_slots if s == "SUPER_FLEX")
        num_qb = sum(1 for s in starter_slots if s == "QB") + sf_count

        rosters, league_users = await asyncio.gather(
            get_rosters(league["league_id"]),
            get_league_users(league["league_id"])
        )

        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue

        user_lookup = {u["user_id"]: u for u in league_users}
        roster_lookup = {r["roster_id"]: r for r in rosters}
        my_user = user_lookup.get(user_id)
        my_team_name = (my_user or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")

        wins = my_roster.get("settings", {}).get("wins", 0)
        losses = my_roster.get("settings", {}).get("losses", 0)
        playoff_spots = league.get("settings", {}).get("playoff_teams", 6)
        total_teams = len(rosters)

        sorted_rosters = sorted(rosters, key=lambda r: (-(r.get("settings") or {}).get("wins", 0), -(r.get("settings") or {}).get("fpts", 0)))
        my_rank = next((i + 1 for i, r in enumerate(sorted_rosters) if r["roster_id"] == my_roster["roster_id"]), total_teams)
        in_playoffs = my_rank <= playoff_spots

        taxi_ids = set(str(pid) for pid in (my_roster.get("taxi") or []))
        starter_ids = set(str(pid) for pid in (my_roster.get("starters") or []))

        def fmt_player(pid):
            p = players_db.get(str(pid))
            if not p:
                return None
            pts = proj_map.get(str(pid), 0)
            return f"{player_name(p)} ({p.get('position','?')}, {p.get('team','FA')}, {pts:.1f}pts, age {p.get('age','?')})"

        my_starters = [s for pid in starter_ids if (s := fmt_player(pid)) is not None]
        my_bench = [s for pid in (my_roster.get("players") or [])
                   if str(pid) not in starter_ids and str(pid) not in taxi_ids
                   if (s := fmt_player(pid)) is not None]

        # Position counts
        pos_counts = {}
        for pid in (my_roster.get("players") or []):
            if str(pid) in taxi_ids:
                continue
            p = players_db.get(str(pid))
            if p:
                pos = p.get("position", "")
                pos_counts[pos] = pos_counts.get(pos, 0) + 1

        # Other teams summary (for trade targets)
        other_teams = []
        for r in sorted_rosters[:6]:  # top 6 teams
            if r["owner_id"] == user_id:
                continue
            owner = user_lookup.get(r["owner_id"])
            team_name = (owner or {}).get("metadata", {}).get("team_name") or (owner or {}).get("display_name", "Unknown")
            r_wins = (r.get("settings") or {}).get("wins", 0)
            r_losses = (r.get("settings") or {}).get("losses", 0)
            r_pos = {}
            for pid in (r.get("players") or []):
                if str(pid) in set(str(p) for p in (r.get("taxi") or [])):
                    continue
                p = players_db.get(str(pid))
                if p:
                    pos = p.get("position", "")
                    r_pos[pos] = r_pos.get(pos, 0) + 1
            other_teams.append(f"{team_name} ({r_wins}-{r_losses}): QB={r_pos.get('QB',0)} RB={r_pos.get('RB',0)} WR={r_pos.get('WR',0)} TE={r_pos.get('TE',0)}")

        league_summaries.append({
            "name": league["name"],
            "format": f"{'Dynasty' if is_dynasty else 'Redraft'} · {scoring_type} · {'2QB/SF' if num_qb >= 2 else '1QB'} · {total_teams} teams",
            "record": f"{wins}-{losses}",
            "rank": f"#{my_rank}/{total_teams}",
            "in_playoffs": in_playoffs,
            "playoff_spots": playoff_spots,
            "team_name": my_team_name,
            "starters": my_starters,
            "bench": my_bench,
            "pos_counts": pos_counts,
            "other_teams": other_teams,
        })

    if not league_summaries:
        raise HTTPException(status_code=404, detail="No leagues found")

    # Build prompt
    prompt = f"""You are an expert fantasy football analyst. Analyze the following team data for user "{user.get('display_name', req.username)}" and provide trade suggestions for each league.

For each league, provide:
1. A ONE-LINE SUMMARY of the team's situation and biggest trade need
2. 2-3 SPECIFIC trade suggestions including: who to target, what to offer, and why

Focus on:
- Position surplus vs needs
- Win-now vs rebuild based on record and roster age
- Specific players they should target or move
- Whether they should be buyers or sellers

Keep each league concise but actionable. Use player names where possible.

=== LEAGUE DATA ===

{chr(10).join(f'''
League: {l["name"]}
Format: {l["format"]}
Record: {l["record"]} (Rank {l["rank"]}) {"✅ In playoffs" if l["in_playoffs"] else f"❌ Outside playoffs (top {l['playoff_spots']} qualify)"}

My Starters: {", ".join(l["starters"][:8]) if l["starters"] else "N/A"}
My Bench: {", ".join(l["bench"][:8]) if l["bench"] else "N/A"}
Position Counts: {" | ".join(f"{k}:{v}" for k,v in sorted(l["pos_counts"].items()) if k in ("QB","RB","WR","TE"))}

Other Teams (for trade context):
{chr(10).join("  " + t for t in l["other_teams"])}
---''' for l in league_summaries)}

Respond with clear section headers for each league. Be specific and actionable."""

    # Call Claude
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set in environment")

    client = anthropic_sdk.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    analysis_text = message.content[0].text if message.content else "No analysis returned."

    # Parse into per-league sections
    sections = []
    current_section = None
    current_lines = []

    for line in analysis_text.split("\n"):
        # Detect league headers
        is_header = any(l["name"].lower() in line.lower() for l in league_summaries) and (line.startswith("#") or line.strip().startswith("**") or line.isupper() or "league" in line.lower())
        matched_league = next((l["name"] for l in league_summaries if l["name"].lower() in line.lower() and (line.startswith("#") or "**" in line or line.strip() == line.strip().upper())), None)

        if matched_league and current_section:
            sections.append({"league": current_section, "content": "\n".join(current_lines).strip()})
            current_section = matched_league
            current_lines = []
        elif matched_league:
            current_section = matched_league
            current_lines = []
        else:
            current_lines.append(line)

    if current_section:
        sections.append({"league": current_section, "content": "\n".join(current_lines).strip()})

    # If parsing failed just return raw
    if not sections:
        sections = [{"league": "All Leagues", "content": analysis_text}]

    return {
        "username": user.get("display_name", req.username),
        "week": week,
        "leagues_analyzed": len(league_summaries),
        "sections": sections,
        "raw": analysis_text,
    }
