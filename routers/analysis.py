from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncio
import math
from services.sleeper_client import *

router = APIRouter(prefix="/api", tags=["analysis"])

SLOT_ELIGIBILITY = {
    "QB": ["QB"], "RB": ["RB"], "WR": ["WR"], "TE": ["TE"],
    "K": ["K"], "DEF": ["DEF"],
    "FLEX": ["RB", "WR", "TE"],
    "SUPER_FLEX": ["QB", "RB", "WR", "TE"],
    "REC_FLEX": ["WR", "TE"],
    "WRRB_FLEX": ["WR", "RB"],
    "DL": ["DL"], "LB": ["LB"], "DB": ["DB"],
    "IDP_FLEX": ["DL", "LB", "DB"],
}

ALL_POS = ("QB", "RB", "WR", "TE", "K", "DEF", "DL", "LB", "DB")
ALL_POS_SET = set(ALL_POS)
IDP_POS = ("DL", "LB", "DB")


def positions_of(item) -> set:
    """Every fantasy position a player (or a pool row with an 'id') can fill — multi-eligible IDPs
    such as DL/LB count for both. Falls back to the row's own position."""
    if not item:
        return set()
    db = get_cached(players_cache, "players") or {}
    p = db.get(str(item.get("id"))) if item.get("id") is not None else None
    fps = (p or {}).get("fantasy_positions") or item.get("fantasy_positions") or []
    out = set(fps)
    if item.get("position"):
        out.add(item["position"])
    return out


def eligible_for(item, slot) -> bool:
    return bool(positions_of(item) & set(SLOT_ELIGIBILITY.get(slot, [slot])))


def league_positions(league) -> set:
    """Positions this league actually starts (union of what its lineup slots accept)."""
    out = set()
    for sl in league.get("roster_positions") or []:
        if sl not in ("BN", "IR", "TAXI"):
            out |= set(SLOT_ELIGIBILITY.get(sl, [sl]))
    return out

NFL_TEAMS = {"ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB","HOU","IND","JAX","KC","LV","LAC","LAR",
             "MIA","MIN","NE","NO","NYG","NYJ","PHI","PIT","SEA","SF","TB","TEN","WAS"}

async def bye_teams_for(season: str, week: int) -> set:
    """NFL teams on bye this week = teams with no game in Sleeper's schedule feed.
    Falls back to an empty set (so nothing is wrongly flagged) if the feed is unavailable."""
    games = await get_schedule(season, week)
    if not games:
        return set()
    playing = {t for g in games for t in (g.get("home"), g.get("away")) if t}
    return NFL_TEAMS - playing

def is_on_bye(p: dict, byes: set, week: int) -> bool:
    """Schedule-derived byes first; the player DB's bye_week as a fallback when the feed is down."""
    if byes:
        return (p.get("team") or "") in byes
    bw = p.get("bye_week")
    try:
        return bool(bw) and int(bw) == week
    except (TypeError, ValueError):
        return False

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

class UserPlayerRequest(BaseModel):
    username: str
    player_name: str
    week: Optional[int] = None

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
    byes = await bye_teams_for(season, week)
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
            if not p or not pid or str(pid) == "0":
                continue
            if is_on_bye(p, byes, week):
                on_bye.append({"id": pid, "name": player_name(p), "position": p.get("position"), "team": p.get("team")})

        if on_bye:
            results.append({"league": league["name"], "team": my_team_name, "on_bye": on_bye})

    return {"week": week, "bye_teams": sorted(byes), "results": results}

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

    byes = await bye_teams_for(season, week)
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
            inj = (p.get("injury_status") or "").upper()
            team = p.get("team")
            if is_on_bye(p, byes, week):
                reason = f"On bye (week {week})"
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
            best = next((p for p in all_players if eligible_for(p, slot) and p["id"] not in assigned), None)
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
    """Projected record (pre-game projections, frozen) plus a live 'expected' record where players who
    have finished use actual points, in-progress players use banked + un-played share of projection,
    and players yet to play use their projection."""
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week
    week_completed = week < current_week
    FULL_GAME_SNAPS = 64.0

    proj_array, stats_array, schedule = await asyncio.gather(
        get_projections(season, week), get_stats(season, week), get_schedule(season, week)
    )
    stats_map = build_stats_map(stats_array)
    team_status = {}
    for g in schedule:
        for t in (g.get("home"), g.get("away")):
            if t:
                team_status[t] = (g.get("status") or "").lower()
    have_schedule = bool(team_status)
    teams_played = {(players_db.get(pid) or {}).get("team") for pid, st in stats_map.items() if (st.get("gp") or 0) >= 1}

    def game_state(pid, p):
        if week_completed:
            return "final"
        st = team_status.get(p.get("team"))
        if st in ("complete", "final", "post_game"):
            return "final"
        if st in ("in_game", "in_progress", "live", "halftime"):
            return "live"
        if st in ("pre_game", "scheduled"):
            return "pre"
        if (stats_map.get(pid, {}).get("gp") or 0) >= 1 or p.get("team") in teams_played:
            return "final" if have_schedule else "live"
        return "pre"

    def progress(pid, p):
        snaps = (stats_map.get(pid) or {}).get("tm_off_snp") or 0
        if not snaps:
            for q, qs in stats_map.items():
                if (players_db.get(q) or {}).get("team") == p.get("team") and (qs.get("tm_off_snp") or 0) > 0:
                    snaps = qs["tm_off_snp"]; break
        return min(max(snaps / FULL_GAME_SNAPS, 0.05), 0.97) if snaps else 0.5

    results = []
    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)

        rosters, league_users, matchups = await asyncio.gather(
            get_rosters(league["league_id"]), get_league_users(league["league_id"]), get_matchups(league["league_id"], week)
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        if not my_matchup or my_matchup.get("matchup_id") is None:
            continue
        opp_matchup = next((m for m in matchups if m.get("matchup_id") == my_matchup["matchup_id"] and m["roster_id"] != my_roster["roster_id"]), None)
        if not opp_matchup:
            continue

        user_lookup = {u["user_id"]: u for u in league_users}
        roster_lookup = {r["roster_id"]: r for r in rosters}
        opp_roster = roster_lookup.get(opp_matchup["roster_id"])
        opp_user = user_lookup.get(opp_roster["owner_id"]) if opp_roster else None
        opp_name = (opp_user or {}).get("metadata", {}).get("team_name") or (opp_user or {}).get("display_name", "Opponent")

        def side(m):
            pts_map = m.get("players_points") or {}
            proj_total = exp_total = 0.0
            pre = live = final = 0
            for pid in (m.get("starters") or []):
                pid = str(pid)
                if not pid or pid == "0":
                    continue
                p = players_db.get(pid) or {}
                proj = proj_map.get(pid, 0)
                actual = float(pts_map.get(pid, 0) or 0)
                proj_total += proj
                state = game_state(pid, p)
                if state == "final":
                    exp_total += actual; final += 1
                elif state == "live":
                    exp_total += actual + max(proj * (1 - progress(pid, p)), 0); live += 1
                else:
                    exp_total += proj; pre += 1
            # Sleeper's matchup total is authoritative for banked points once anything has scored
            banked = float(m.get("points") or 0)
            return {"proj": round(proj_total, 2), "exp": round(exp_total, 2), "banked": round(banked, 2),
                    "pre": pre, "live": live, "final": final}

        me, opp = side(my_matchup), side(opp_matchup)
        # expected total uses Sleeper's banked points + remaining share so it matches the app's score
        def exp_with_banked(sd, m):
            if week_completed:
                return round(float(m.get("points") or 0), 2)
            remaining = sd["exp"] - sum(float(v or 0) for k, v in (m.get("players_points") or {}).items() if str(k) in {str(x) for x in (m.get("starters") or [])})
            return round(sd["banked"] + max(remaining, 0), 2)
        my_exp, opp_exp = exp_with_banked(me, my_matchup), exp_with_banked(opp, opp_matchup)

        proj_win = me["proj"] > opp["proj"]
        proj_diff = me["proj"] - opp["proj"]
        win_prob = round(1 / (1 + math.exp(-proj_diff / 8)) * 100)

        all_final = (me["pre"] + me["live"] + opp["pre"] + opp["live"]) == 0
        exp_diff = my_exp - opp_exp
        exp_win = my_exp > opp_exp
        exp_prob = (100 if exp_diff > 0 else 0 if exp_diff < 0 else 50) if all_final else round(1 / (1 + math.exp(-exp_diff / 8)) * 100)
        status = ("FINAL" if all_final else "LIVE" if (me["live"] + opp["live"]) > 0 or (me["final"] + opp["final"]) > 0 else "PREGAME")

        actual_won = actual_tied = surprise = None
        my_actual = opp_actual = None
        if all_final:
            my_actual, opp_actual = my_exp, opp_exp
            actual_won = my_actual > opp_actual
            actual_tied = my_actual == opp_actual
            if (proj_win != actual_won) and abs(proj_diff) > 5:
                surprise = "upset_win" if actual_won else "upset_loss"

        _mu = user_lookup.get(user_id)
        my_team_name = (_mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        results.append({
            "league": league["name"], "team": my_team_name, "opp_name": opp_name,
            "my_proj": me["proj"], "opp_proj": opp["proj"], "proj_win": proj_win, "win_prob": win_prob,
            "my_exp": my_exp, "opp_exp": opp_exp, "exp_win": exp_win, "exp_prob": exp_prob,
            "flipped": proj_win != exp_win,
            "status": status, "my_left": me["pre"] + me["live"], "opp_left": opp["pre"] + opp["live"],
            "my_actual": my_actual, "opp_actual": opp_actual, "actual_won": actual_won, "actual_tied": actual_tied,
            "surprise": surprise,
        })

    proj_w = sum(1 for r in results if r["proj_win"]); exp_w = sum(1 for r in results if r["exp_win"])
    finals = [r for r in results if r["status"] == "FINAL"]
    return {
        "week": week, "week_completed": week_completed, "have_schedule": have_schedule,
        "summary": {
            "leagues": len(results),
            "projected": f"{proj_w}-{len(results) - proj_w}",
            "expected": f"{exp_w}-{len(results) - exp_w}",
            "final": f"{sum(1 for r in finals if r['actual_won'])}-{sum(1 for r in finals if not r['actual_won'] and not r['actual_tied'])}",
            "finals": len(finals), "live": sum(1 for r in results if r["status"] == "LIVE"),
            "flipped_up": sum(1 for r in results if r["flipped"] and r["exp_win"]),
            "flipped_down": sum(1 for r in results if r["flipped"] and not r["exp_win"]),
        },
        "results": results,
    }

# ── THERE'S A CHANCE ──────────────────────────────────────────────────────────

@router.post("/analysis/theres-a-chance")
async def get_theres_a_chance(req: UserRequest):
    """Live matchup read with a real win probability.
    Each starter is pre-game (full projection ± his season std dev), in progress (banked points +
    the un-played share of his projection), or final (actual points only). Game state comes from
    Sleeper's schedule feed; progress of a live game is estimated from team offensive snaps."""
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week
    weeks_completed = max(0, min(week - 1, current_week - 1))
    FULL_GAME_SNAPS = 64.0
    SKIP_BELOW = 3.0      # win % below which a losing league is pushed to the "ignore" list

    proj_array, stats_array, schedule, weekly_by_player = await asyncio.gather(
        get_projections(season, week), get_stats(season, week), get_schedule(season, week),
        _weekly_stats_by_player(season, weeks_completed),
    )
    stats_map = build_stats_map(stats_array)

    team_status = {}
    for g in schedule:
        for t in (g.get("home"), g.get("away")):
            if t:
                team_status[t] = (g.get("status") or "").lower()
    have_schedule = bool(team_status)
    teams_played = {(players_db.get(pid) or {}).get("team") for pid, st in stats_map.items() if (st.get("gp") or 0) >= 1}

    def game_state(pid, p):
        st = team_status.get(p.get("team"))
        if st in ("complete", "final", "post_game"):
            return "final"
        if st in ("in_game", "in_progress", "live", "halftime"):
            return "live"
        if st in ("pre_game", "scheduled"):
            return "pre"
        if (stats_map.get(pid, {}).get("gp") or 0) >= 1 or p.get("team") in teams_played:
            return "final" if have_schedule else "live"
        return "pre"

    def game_progress(pid, p):
        """0..1 share of a live game already played, from team offensive snaps (0.5 if unknown)."""
        st = stats_map.get(pid) or {}
        snaps = st.get("tm_off_snp") or st.get("tm_def_snp") or 0
        if not snaps:
            # borrow any teammate's team-snap count
            for q, qs in stats_map.items():
                if (players_db.get(q) or {}).get("team") == p.get("team") and (qs.get("tm_off_snp") or 0) > 0:
                    snaps = qs["tm_off_snp"]; break
        return min(max(snaps / FULL_GAME_SNAPS, 0.05), 0.97) if snaps else 0.5

    results, skipped, finished = [], [], []
    for league in leagues:
        if league.get("status") == "complete":
            continue
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)

        rosters, league_users, matchups = await asyncio.gather(
            get_rosters(league["league_id"]), get_league_users(league["league_id"]), get_matchups(league["league_id"], week)
        )
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        my_matchup = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        if not my_matchup or my_matchup.get("matchup_id") is None:
            continue
        opp_matchup = next((m for m in matchups if m.get("matchup_id") == my_matchup["matchup_id"] and m["roster_id"] != my_roster["roster_id"]), None)
        if not opp_matchup:
            continue

        user_lookup = {u["user_id"]: u for u in league_users}
        roster_lookup = {r["roster_id"]: r for r in rosters}
        opp_roster = roster_lookup.get(opp_matchup["roster_id"])
        opp_user = user_lookup.get(opp_roster["owner_id"]) if opp_roster else None
        opp_name = (opp_user or {}).get("metadata", {}).get("team_name") or (opp_user or {}).get("display_name", "Opponent")
        _mu = user_lookup.get(user_id)
        my_team_name = (_mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")

        def side(matchup):
            pts_map = matchup.get("players_points") or {}
            banked, exp_rem, var, pre, live, done = 0.0, 0.0, 0.0, [], [], 0
            for pid in (matchup.get("starters") or []):
                pid = str(pid)
                if not pid or pid == "0":
                    continue
                p = players_db.get(pid) or {}
                actual = float(pts_map.get(pid, 0) or 0)
                proj = proj_map.get(pid, 0)
                avg, sd, gp, _ = _season_line(weekly_by_player.get(pid), ss)
                sd = sd if (sd is not None and gp >= 2) else max(0.45 * proj, 2.0)
                state = game_state(pid, p)
                row = {"id": pid, "name": player_name(p), "position": p.get("position", "UNK"), "team": p.get("team", ""),
                       "proj_pts": round(proj, 1), "actual": round(actual, 2), "state": state}
                if state == "final":
                    banked += actual; done += 1
                elif state == "pre":
                    exp_rem += proj; var += sd ** 2; pre.append(row)
                else:
                    frac = game_progress(pid, p)
                    rem = max(proj * (1 - frac), 0.0)
                    banked += actual; exp_rem += rem; var += (sd * (1 - frac) ** 0.5) ** 2
                    row.update({"progress": round(frac * 100), "remaining_proj": round(rem, 1)})
                    live.append(row)
            return {"banked": round(banked, 2), "exp_remaining": round(exp_rem, 1), "expected": round(banked + exp_rem, 1),
                    "sd": round(var ** 0.5, 1), "pre": pre, "live": live, "done": done}

        me, opp = side(my_matchup), side(opp_matchup)
        my_live_pts = float(my_matchup.get("points") or 0)
        opp_live_pts = float(opp_matchup.get("points") or 0)
        # Sleeper's matchup.points is authoritative for banked totals; use it when it has data
        if my_live_pts > 0 or opp_live_pts > 0:
            me["expected"] = round(my_live_pts + me["exp_remaining"], 1); me["banked"] = round(my_live_pts, 2)
            opp["expected"] = round(opp_live_pts + opp["exp_remaining"], 1); opp["banked"] = round(opp_live_pts, 2)

        diff = me["expected"] - opp["expected"]
        tot_sd = (me["sd"] ** 2 + opp["sd"] ** 2) ** 0.5
        all_done = not me["pre"] and not me["live"] and not opp["pre"] and not opp["live"]
        if all_done or tot_sd < 1e-6:
            win_prob = 100.0 if diff > 0 else 0.0 if diff < 0 else 50.0
        else:
            win_prob = round(100 * 0.5 * (1 + math.erf(diff / (tot_sd * math.sqrt(2)))), 1)

        if all_done:
            status = "WON" if diff > 0 else "LOST" if diff < 0 else "TIED"
        elif win_prob >= 95:   status = "LOCKED IN"
        elif win_prob >= 70:   status = "WINNING"
        elif win_prob >= 45:   status = "COIN FLIP"
        elif win_prob >= 25:   status = "THERE'S A CHANCE"
        elif win_prob >= 8:    status = "LONG SHOT"
        else:                  status = "ELIMINATED"

        # what has to happen: points per remaining player needed to pull even
        my_left = len(me["pre"]) + len(me["live"]); opp_left = len(opp["pre"]) + len(opp["live"])
        need = None
        if diff < 0 and my_left > 0:
            need = round((opp["expected"] - me["banked"]) / my_left, 1)

        entry = {
            "league": league["name"], "team": my_team_name, "opp_name": opp_name,
            "status": status, "win_prob": win_prob,
            "my_live": me["banked"], "opp_live": opp["banked"],
            "my_exp": me["expected"], "opp_exp": opp["expected"],
            "my_remaining_proj": me["exp_remaining"], "opp_remaining_proj": opp["exp_remaining"],
            "my_sd": me["sd"], "opp_sd": opp["sd"],
            "my_remaining": me["pre"], "opp_remaining": opp["pre"],
            "my_in_progress": me["live"], "opp_in_progress": opp["live"],
            "my_left": my_left, "opp_left": opp_left,
            "lead": round(me["banked"] - opp["banked"], 2), "exp_margin": round(diff, 1),
            "need_per_player": need,
            # legacy keys some views/digest still read
            "my_max": me["expected"], "opp_max": opp["expected"],
        }
        if all_done:
            finished.append(entry)
        elif status == "ELIMINATED" and win_prob < SKIP_BELOW:
            skipped.append(entry)
        else:
            results.append(entry)

    # Closest games first — that's where attention goes
    results.sort(key=lambda r: abs(r["win_prob"] - 50))
    skipped.sort(key=lambda r: -r["win_prob"])
    finished.sort(key=lambda r: (r["status"] != "WON", r["league"]))
    return {
        "week": week, "have_schedule": have_schedule,
        "summary": {
            "in_play": len(results), "finished": len(finished), "ignored": len(skipped),
            "won": sum(1 for r in finished if r["status"] == "WON"), "lost": sum(1 for r in finished if r["status"] == "LOST"),
            "favored": sum(1 for r in results if r["win_prob"] >= 50), "underdog": sum(1 for r in results if r["win_prob"] < 50),
            "expected_wins": round(sum(r["win_prob"] for r in results) / 100 + sum(1 for r in finished if r["status"] == "WON"), 1),
        },
        "results": results, "skipped": skipped, "finished": finished,
        "note": "Win % = chance your final beats theirs: banked points + remaining projection per player, with each player's "
                "season std dev as uncertainty. In-progress players keep the un-played share of their projection "
                "(estimated from team snaps). Leagues under 3% are listed as ignorable; finished matchups are at the bottom.",
    }


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
                if eligible_for(c, starter_slots[i]):
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


# ── SEASON STATS HELPERS (shared by Optimal Lineup + Upgrade Recs) ────────────

async def _weekly_stats_by_player(season, weeks_completed):
    """{player_id: [weekly raw-stat dicts for weeks the player actually played (gp>=1)]}"""
    by_player = {}
    if weeks_completed <= 0:
        return by_player
    for week_data in await asyncio.gather(*[get_stats(season, w) for w in range(1, weeks_completed + 1)]):
        for pid, st in build_stats_map(week_data).items():
            if (st.get("gp") or 0) >= 1:
                by_player.setdefault(pid, []).append(st)
    return by_player


def _season_line(weekly, ss):
    """Score each played week with the league's scoring_settings.
    Returns (avg_per_game, std_dev, games_played, [weekly points]).
    std_dev is sample standard deviation (None with fewer than 2 games)."""
    if not weekly:
        return 0.0, None, 0, []
    pts = [round(sum(ss.get(k, 0) * v for k, v in st.items() if isinstance(v, (int, float))), 2) for st in weekly]
    gp = len(pts)
    avg = sum(pts) / gp
    sd = (sum((x - avg) ** 2 for x in pts) / (gp - 1)) ** 0.5 if gp >= 2 else None
    return round(avg, 1), (round(sd, 1) if sd is not None else None), gp, pts

@router.post("/analysis/optimal-lineup")
async def get_optimal_lineup(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week

    weeks_completed = max(0, min(week - 1, current_week - 1))

    proj_array, stats_array = await asyncio.gather(get_projections(season, week), get_stats(season, week))
    stats_map = build_stats_map(stats_array)
    has_played = lambda pid: stats_map.get(str(pid), {}).get("gp", 0) >= 1

    weekly_by_player = await _weekly_stats_by_player(season, weeks_completed)

    results, optimal_leagues = [], []

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
            avg, sd, gp, _ = _season_line(weekly_by_player.get(pid), ss)
            # Ranking uses the week projection (actual points once a player has played);
            # season average / games played are informational only.
            pts = actual_pts.get(pid, 0) if played else proj
            pool.append({
                "id": pid, "name": player_name(p), "position": p.get("position", "UNK"), "team": p.get("team", "FA"),
                "pts": pts, "proj": proj, "avg": avg, "std": sd, "gp": gp,
                "has_played": played, "injury_status": p.get("injury_status"), "is_starter": pid in starter_set,
            })

        lineup = compute_lineup(starter_slots, starters_ordered, pool, has_played, key="pts")

        current_pts = round(sum((s["current"] or {}).get("pts", 0) for s in lineup), 2)
        optimal_pts = round(sum((s["optimal"] or {}).get("pts", 0) for s in lineup), 2)
        gain = round(optimal_pts - current_pts, 2)

        moves, swaps = lineup_moves(lineup)
        used = {s["optimal"]["id"] for s in lineup if s["optimal"]}
        bench = [p for p in pool if p["id"] not in used]

        # ── Taxi players and free agents who out-project the optimal roster lineup ──
        FA_MIN_GAIN = 1.5
        lg_pos = league_positions(league)
        rostered = {str(x) for r in rosters for x in (r.get("players") or [])}
        def ext(pid, pp, source):
            return {"id": pid, "name": player_name(pp), "position": pp.get("position"), "team": pp.get("team"),
                    "pts": round(proj_map.get(pid, 0), 1), "injury_status": pp.get("injury_status"), "source": source}
        ok = lambda pid, pp: (pp.get("position") in lg_pos and pp.get("team")
                              and proj_map.get(pid, 0) >= 3 and not has_played(pid)
                              and (pp.get("injury_status") or "").upper() not in ("OUT", "IR", "PUP", "SUS"))
        taxi_pool = [ext(pid, pp, "taxi") for pid in taxi_ids if (pp := players_db.get(pid)) and ok(pid, pp)]
        fa_only = [ext(pid, pp, "FA") for pid, pp in players_db.items() if pid not in rostered and ok(pid, pp)]
        # taxi first (already yours — just promote), then FAs; within each, best projection first
        fa_pool = sorted(taxi_pool, key=lambda x: -x["pts"]) + sorted(fa_only, key=lambda x: -x["pts"])
        fa_upgrades, used_fa = [], set()
        # weakest optimal slots first so the best FA replaces the worst starter he is eligible for
        for sl in sorted(lineup, key=lambda x: (x["optimal"] or {}).get("pts", 0)):
            if sl["locked"]:
                continue
            cur = sl["optimal"]; cur_pts = (cur or {}).get("pts", 0)
            elig = SLOT_ELIGIBILITY.get(sl["slot"], [sl["slot"]])
            cands = [f for f in fa_pool if eligible_for(f, sl["slot"]) and f["id"] not in used_fa and f["pts"] >= cur_pts + FA_MIN_GAIN]
            best = max(cands, key=lambda f: (f["pts"], f["source"] == "taxi")) if cands else None
            if best:
                used_fa.add(best["id"])
                fa_upgrades.append({"slot": sl["slot"], "current": cur, "fa": best, "gain": round(best["pts"] - cur_pts, 1)})
        fa_upgrades.sort(key=lambda x: -x["gain"])
        fa_gain = round(sum(x["gain"] for x in fa_upgrades), 1)

        if (gain < 0.5 or not moves) and not fa_upgrades:
            optimal_leagues.append({"league": league["name"], "team": my_team_name, "pts": current_pts})
        else:
            results.append({
                "league": league["name"], "team": my_team_name,
                "optimal_pts": optimal_pts, "current_pts": current_pts, "gain": gain,
                "lineup": [{"slot": s["slot"], "player": s["optimal"], "locked": s["locked"]} for s in lineup],
                "moves": moves, "swaps": swaps, "bench": bench,
                "locked_count": sum(1 for s in lineup if s["locked"]),
                "fa_upgrades": fa_upgrades, "fa_gain": fa_gain,
                "taxi_upgrades": sum(1 for u in fa_upgrades if u["fa"]["source"] == "taxi"),
                "lineup_only": not moves or gain < 0.5,
            })

    return {"week": week, "weeks_completed": weeks_completed, "results": results, "optimal_leagues": optimal_leagues,
            "summary": {"leagues": len(results) + len(optimal_leagues), "need_lineup_changes": sum(1 for r in results if not r["lineup_only"]),
                        "have_fa_upgrades": sum(1 for r in results if r["fa_upgrades"]), "already_optimal": len(optimal_leagues)}}

# ── MY POSITION NEEDS ─────────────────────────────────────────────────────────

@router.post("/analysis/position-needs")
async def get_position_needs(req: UserRequest):
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]

    needs_by_pos = {pos: [] for pos in ALL_POS}

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
            elif pos in ("RB", "WR", "TE", "DL", "LB", "DB"):
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

    weekly_by_player = await _weekly_stats_by_player(season, weeks_completed)

    results = []
    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        starter_slots = [s for s in league.get("roster_positions", []) if s not in ("BN", "IR", "TAXI")]

        def score(pid):
            """Returns (week_proj, season_avg_per_game, std_dev, floor, games_played).
            floor = the LOWER of projection and season average — recommendations are
            conservative. Players with 0 games played fall back to projection."""
            wk = proj_map.get(pid, 0)
            avg, sd, gp, _ = _season_line(weekly_by_player.get(pid), ss)
            floor = min(wk, avg) if gp > 0 else wk
            return round(wk, 1), avg, sd, round(floor, 1), gp

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
            wk, avg, sd, bl, gp = score(pid)
            pool.append({
                "id": pid, "name": player_name(p), "position": p.get("position", "UNK"), "team": p.get("team", ""),
                "week_pts": wk, "ytd_avg": avg, "std": sd, "gp": gp, "blended": bl, "pts": bl,
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
    POS = list(ALL_POS)
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
    RELEVANT = ALL_POS_SET

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
             if pid not in rostered and p.get("position") in RELEVANT and p.get("position") in league_positions(league)
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
            fa_ups = [f for f in fas if eligible_for(f, x["slot"]) and f["pts"] > floor][:2]
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

        RELEVANT_POSITIONS = ALL_POS_SET

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
        next_byes = await bye_teams_for(season, next_week)
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
            nxt_pool.append({**p, "pts": next_proj_map.get(p["id"], 0), "is_starter": p["id"] in nxt_set,
                             "on_bye": is_on_bye(pl, next_byes, next_week)})
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


# ── WAIVER WATCH ──────────────────────────────────────────────────────────────

def _recent_avg(weekly_pts, n=2):
    tail = weekly_pts[-n:]
    return round(sum(tail) / len(tail), 1) if tail else 0.0


@router.post("/analysis/waiver-watch")
async def get_waiver_watch(req: UserRequest):
    """Free agents whose production (season avg or last-2-week avg, league-scored) beats the
    weakest starter they could replace. Trend-based, so it catches risers projections lag on."""
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week
    weeks_completed = max(0, min(week - 1, current_week - 1))
    RELEVANT = ALL_POS_SET
    MIN_GAIN = 1.0

    proj_array, stats_array, weekly_by_player, trending_add, trending_drop = await asyncio.gather(
        get_projections(season, week), get_stats(season, week),
        _weekly_stats_by_player(season, weeks_completed),
        get_trending("add", 24, 100), get_trending("drop", 24, 100),
    )
    stats_map = build_stats_map(stats_array)
    has_played = lambda pid: stats_map.get(str(pid), {}).get("gp", 0) >= 1
    trend_add = {str(t.get("player_id")): t.get("count", 0) for t in trending_add}
    trend_drop = {str(t.get("player_id")): t.get("count", 0) for t in trending_drop}

    # Candidate FA universe: relevant position, on an NFL team, and has either a projection or a played game
    proj_ids = {str(e.get("player_id")) for e in proj_array if e.get("player_id")}
    candidates = [pid for pid, p in players_db.items()
                  if p.get("position") in RELEVANT and p.get("team") and (pid in weekly_by_player or pid in proj_ids)]

    results, all_hits = [], []
    for league in leagues:
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
        starters_ordered = [str(x) for x in ((my_matchup or my_roster).get("starters") or [])]
        rostered = {str(pid) for r in rosters for pid in (r.get("players") or [])}
        taxi_ids = {str(t) for t in (my_roster.get("taxi") or [])}
        ir_ids = {str(t) for t in (my_roster.get("reserve") or [])}

        def line(pid):
            p = players_db.get(pid) or {}
            avg, sd, gp, wk_pts = _season_line(weekly_by_player.get(pid), ss)
            proj = round(proj_map.get(pid, 0), 1)
            recent = _recent_avg(wk_pts)
            floor = min(proj, avg) if gp > 0 else proj
            return {"id": pid, "name": player_name(p), "position": p.get("position", "UNK"), "team": p.get("team", "FA"),
                    "injury_status": p.get("injury_status"), "proj": proj, "avg": avg, "std": sd, "gp": gp,
                    "recent": recent, "floor": round(floor, 1)}

        # Current starters by slot → weakest starter each FA position could replace
        slot_starters = []
        for i, slot in enumerate(starter_slots):
            pid = starters_ordered[i] if i < len(starters_ordered) else "0"
            slot_starters.append((slot, line(pid) if pid and pid != "0" and pid in players_db else None))

        def weakest_for(fa_row):
            opts = [(st["floor"] if st else -1.0, slot, st) for slot, st in slot_starters if eligible_for(fa_row, slot)]
            if not opts:
                return None
            return min(opts, key=lambda t: t[0])

        bench = [line(str(pid)) for pid in (my_roster.get("players") or [])
                 if str(pid) not in set(starters_ordered) and str(pid) not in taxi_ids and str(pid) not in ir_ids]
        bench = [b for b in bench if b["name"]]

        hits = []
        for pid in candidates:
            if pid in rostered:
                continue
            fa = line(pid)
            if fa["gp"] < 1 or fa["proj"] <= 0 or has_played(pid):
                continue
            if (fa["injury_status"] or "").lower() in ("out", "ir", "pup", "sus"):
                continue
            w = weakest_for(fa)
            if w is None:
                continue
            weakest_val, slot, st = w
            production = max(fa["avg"], fa["recent"])
            gain = round(production - max(weakest_val, 0), 1)
            if gain < MIN_GAIN:
                continue
            same_pos_bench = [b for b in bench if b["position"] == fa["position"]]
            drop_pool = same_pos_bench or bench
            drop = min(drop_pool, key=lambda b: (b["floor"], b["avg"])) if drop_pool else None
            trend = "rising" if fa["gp"] >= 3 and fa["recent"] >= fa["avg"] * 1.25 else \
                    "fading" if fa["gp"] >= 3 and fa["recent"] <= fa["avg"] * 0.75 else "steady"
            hits.append({
                **fa, "production": round(production, 1), "gain": gain, "trend": trend,
                "replaces": {"slot": slot, "name": st["name"] if st else None, "floor": round(weakest_val, 1) if st else 0},
                "drop_candidate": {"name": drop["name"], "position": drop["position"], "floor": drop["floor"], "avg": drop["avg"], "gp": drop["gp"]} if drop else None,
                "trending_adds": trend_add.get(pid, 0), "trending_drops": trend_drop.get(pid, 0),
                "under_radar": trend_add.get(pid, 0) == 0,
            })
        hits.sort(key=lambda h: -h["gain"])
        top = hits[:6]
        for h in top:
            all_hits.append({**h, "league": league["name"], "team": my_team_name})
        results.append({
            "league": league["name"], "team": my_team_name, "candidates": top, "total_candidates": len(hits),
            "best_gain": top[0]["gain"] if top else 0,
        })

    results.sort(key=lambda r: -r["best_gain"])
    all_hits.sort(key=lambda h: -h["gain"])
    return {
        "week": week, "weeks_completed": weeks_completed,
        "summary": {
            "leagues": len(results),
            "leagues_with_pickups": sum(1 for r in results if r["candidates"]),
            "total_candidates": sum(r["total_candidates"] for r in results),
            "under_radar": sum(1 for h in all_hits if h["under_radar"]),
            "top": all_hits[:5],
        },
        "results": results,
        "note": "Production = max(season avg, last-2-week avg), league-scored. Gain is vs the weakest starter the player is eligible to replace (using that starter's floor = min(projection, avg)). Players already played, injured OUT, or with no games are excluded.",
    }


# ── PLAYOFF ODDS ──────────────────────────────────────────────────────────────

def _byes_for(spots):
    """Teams that skip round 1 in a standard single-elimination bracket of `spots` teams."""
    if spots <= 1:
        return 0
    n = 1
    while n < spots:
        n *= 2
    return n - spots


def _simulate_league(team_ids, strength, schedule, base_wins, base_pf, playoff_spots, sims, seed, condition=None):
    """Monte Carlo the rest of the regular season.
    strength: {rid: (mu, sd)}; schedule: [[(a, b), ...] per remaining week]; base_wins/base_pf: current totals.
    condition: optional (week_idx, winner_rid, loser_rid) to force one result.
    Returns {rid: {playoff, bye, wins_hist, exp_wins}}."""
    import random
    rng = random.Random(seed)
    byes = _byes_for(playoff_spots)
    tally = {rid: {"playoff": 0, "bye": 0, "wins_sum": 0.0, "hist": {}} for rid in team_ids}
    for _ in range(sims):
        wins = dict(base_wins)
        pf = dict(base_pf)
        for wi, week_games in enumerate(schedule):
            for a, b in week_games:
                mu_a, sd_a = strength[a]; mu_b, sd_b = strength[b]
                sa = rng.gauss(mu_a, sd_a); sb = rng.gauss(mu_b, sd_b)
                pf[a] += sa; pf[b] += sb
                if condition and condition[0] == wi and {a, b} == {condition[1], condition[2]}:
                    winner = condition[1]
                else:
                    winner = a if sa >= sb else b
                wins[winner] = wins.get(winner, 0) + 1
        order = sorted(team_ids, key=lambda r: (-wins.get(r, 0), -pf.get(r, 0)))
        for rank, rid in enumerate(order, start=1):
            t = tally[rid]
            w = wins.get(rid, 0)
            t["wins_sum"] += w
            t["hist"][w] = t["hist"].get(w, 0) + 1
            if rank <= playoff_spots:
                t["playoff"] += 1
            if rank <= byes:
                t["bye"] += 1
    out = {}
    for rid, t in tally.items():
        out[rid] = {
            "playoff_pct": round(100 * t["playoff"] / sims, 1),
            "bye_pct": round(100 * t["bye"] / sims, 1),
            "exp_wins": round(t["wins_sum"] / sims, 1),
            "wins_hist": {int(k): round(100 * v / sims, 1) for k, v in sorted(t["hist"].items())},
        }
    return out


@router.post("/analysis/playoff-odds")
async def get_playoff_odds(req: UserRequest):
    """Monte Carlo playoff odds per league using each team's actual scoring mean ± sd and the real remaining schedule."""
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week
    SIMS = 1500
    proj_array = await get_projections(season, week)

    results = []
    for league in leagues:
        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        settings = league.get("settings", {})
        playoff_spots = settings.get("playoff_teams", 6)
        regular_season_end = max(1, settings.get("playoff_week_start", 15) - 1)
        if week > regular_season_end:
            continue

        rosters, league_users = await asyncio.gather(get_rosters(league["league_id"]), get_league_users(league["league_id"]))
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster or len(rosters) < 2:
            continue
        user_lookup = {u["user_id"]: u for u in league_users}
        team_name = lambda r: (user_lookup.get(r.get("owner_id")) or {}).get("metadata", {}).get("team_name") \
            or (user_lookup.get(r.get("owner_id")) or {}).get("display_name") or f"Team {r['roster_id']}"
        my_team_name = team_name(my_roster)
        team_ids = [r["roster_id"] for r in rosters]

        past_weeks = list(range(1, week))
        future_weeks = list(range(week, regular_season_end + 1))
        past, future = await asyncio.gather(
            asyncio.gather(*[get_matchups(league["league_id"], w) for w in past_weeks]),
            asyncio.gather(*[get_matchups(league["league_id"], w) for w in future_weeks]),
        )

        # Actual weekly scores per team (completed weeks with real points)
        scores = {rid: [] for rid in team_ids}
        for wk_m in past:
            if not wk_m or all((m.get("points") or 0) == 0 for m in wk_m):
                continue
            for m in wk_m:
                if m.get("roster_id") in scores:
                    scores[m["roster_id"]].append(float(m.get("points") or 0))

        # Projected starter totals as the prior
        proj_total = {r["roster_id"]: sum(proj_map.get(str(pid), 0) for pid in (r.get("starters") or []) if pid and pid != "0") for r in rosters}
        all_scores = [x for v in scores.values() for x in v]
        league_mu = sum(all_scores) / len(all_scores) if all_scores else (sum(proj_total.values()) / len(proj_total) or 100)
        if len(all_scores) >= 4:
            league_sd = (sum((x - league_mu) ** 2 for x in all_scores) / (len(all_scores) - 1)) ** 0.5
        else:
            league_sd = league_mu * 0.2

        strength = {}
        for rid in team_ids:
            sc = scores[rid]; n = len(sc)
            prior = proj_total.get(rid) or league_mu
            if n == 0:
                mu, sd = prior, league_sd
            else:
                act_mu = sum(sc) / n
                w = min(n / 4.0, 1.0)                       # trust actuals fully after 4 games
                mu = w * act_mu + (1 - w) * prior
                sd = (sum((x - act_mu) ** 2 for x in sc) / (n - 1)) ** 0.5 if n >= 3 else league_sd
                sd = max(sd, league_sd * 0.5)
            strength[rid] = (mu, sd)

        # Remaining schedule from real matchup ids (skip weeks Sleeper hasn't scheduled yet)
        schedule = []
        for wk_m in future:
            pairs = {}
            for m in wk_m or []:
                if m.get("matchup_id") is not None:
                    pairs.setdefault(m["matchup_id"], []).append(m["roster_id"])
            games = [(a[0], a[1]) for a in pairs.values() if len(a) == 2]
            if games:
                schedule.append(games)

        st_of = lambda r: r.get("settings") or {}
        base_wins = {r["roster_id"]: st_of(r).get("wins", 0) + 0.5 * st_of(r).get("ties", 0) for r in rosters}
        base_pf = {r["roster_id"]: st_of(r).get("fpts", 0) + st_of(r).get("fpts_decimal", 0) / 100.0 for r in rosters}

        seed = int(league["league_id"]) % 100000
        sim = _simulate_league(team_ids, strength, schedule, base_wins, base_pf, playoff_spots, SIMS, seed)
        me = sim[my_roster["roster_id"]]

        # Swing of the next game: odds if I win it vs if I lose it
        next_game, swing = None, None
        if schedule:
            opp = next((b if a == my_roster["roster_id"] else a for a, b in schedule[0] if my_roster["roster_id"] in (a, b)), None)
            if opp is not None:
                opp_r = next(r for r in rosters if r["roster_id"] == opp)
                if_win = _simulate_league(team_ids, strength, schedule, base_wins, base_pf, playoff_spots, 600, seed + 1,
                                          condition=(0, my_roster["roster_id"], opp))[my_roster["roster_id"]]["playoff_pct"]
                if_loss = _simulate_league(team_ids, strength, schedule, base_wins, base_pf, playoff_spots, 600, seed + 2,
                                           condition=(0, opp, my_roster["roster_id"]))[my_roster["roster_id"]]["playoff_pct"]
                mu_me, sd_me = strength[my_roster["roster_id"]]; mu_o, sd_o = strength[opp]
                next_game = {"week": future_weeks[0], "opp_name": team_name(opp_r), "my_mu": round(mu_me, 1), "opp_mu": round(mu_o, 1),
                             "win_prob": round(100 * 0.5 * (1 + math.erf((mu_me - mu_o) / (((sd_me ** 2 + sd_o ** 2) ** 0.5) * math.sqrt(2)))), 1),
                             "playoff_if_win": if_win, "playoff_if_loss": if_loss, "swing": round(if_win - if_loss, 1)}
                swing = next_game["swing"]

        pct = me["playoff_pct"]
        if pct >= 99.5:
            status, color, advice = "CLINCHED", "#00e5a0", "Locked in. Rest starters only if the seed is settled; otherwise play for the bye and points-for tiebreakers."
        elif pct >= 85:
            status, color, advice = "SAFE", "#00e5a0", "Bank FAAB and picks — spend only on upgrades that matter in the playoffs (bye weeks 15–17, matchups)."
        elif pct >= 60:
            status, color, advice = "LIKELY", "#5c9eff", "On track. Fix lineup leaks and make the small waiver upgrades; no need to overpay."
        elif pct >= 35:
            status, color, advice = "BUBBLE", "#ffb347", "Every game swings this. Spend FAAB here first and start the higher-ceiling players when you're the underdog."
        elif pct >= 10:
            status, color, advice = "LONG SHOT", "#ff8c42", "Need help. Chase upside on waivers; if the next game is lost, shift this league to rebuild mode."
        elif pct > 0.5:
            status, color, advice = "FADING", "#ff5c5c", "Mathematically alive only. Stop spending FAAB; move vets for picks before the deadline."
        else:
            status, color, advice = "ELIMINATED", "#ff5c5c", "Out of it. Full pivot: sell every aging asset, play the young guys, maximize next year's draft."

        rank_now = sorted(team_ids, key=lambda r: (-base_wins[r], -base_pf[r])).index(my_roster["roster_id"]) + 1
        others = sorted([(sim[r]["playoff_pct"], team_name(next(x for x in rosters if x["roster_id"] == r)), base_wins[r]) for r in team_ids], key=lambda t: -t[0])

        results.append({
            "league": league["name"], "team": my_team_name,
            "record": f"{st_of(my_roster).get('wins', 0)}-{st_of(my_roster).get('losses', 0)}" + (f"-{st_of(my_roster)['ties']}" if st_of(my_roster).get("ties") else ""),
            "rank": rank_now, "total_teams": len(team_ids), "playoff_spots": playoff_spots, "byes": _byes_for(playoff_spots),
            "games_left": len(schedule), "games_sampled": len(scores[my_roster["roster_id"]]),
            "my_mu": round(strength[my_roster["roster_id"]][0], 1), "my_sd": round(strength[my_roster["roster_id"]][1], 1),
            "league_mu": round(league_mu, 1),
            "playoff_pct": pct, "bye_pct": me["bye_pct"], "exp_wins": me["exp_wins"], "wins_hist": me["wins_hist"],
            "status": status, "color": color, "advice": advice,
            "next_game": next_game,
            "league_table": [{"team": n, "wins": w, "playoff_pct": p} for p, n, w in others],
        })

    order = {lg["name"]: i for i, lg in enumerate(leagues)}
    results.sort(key=lambda r: order.get(r["league"], 10**6))
    return {
        "week": week, "sims": SIMS,
        "summary": {
            "leagues": len(results),
            "clinched_or_safe": sum(1 for r in results if r["playoff_pct"] >= 85),
            "bubble": sum(1 for r in results if 10 <= r["playoff_pct"] < 85),
            "out": sum(1 for r in results if r["playoff_pct"] < 10),
            "avg_playoff_pct": round(sum(r["playoff_pct"] for r in results) / len(results), 1) if results else 0,
            "biggest_swing": max(results, key=lambda r: (r["next_game"] or {}).get("swing", -1))["league"] if any(r["next_game"] for r in results) else None,
        },
        "results": results,
        "note": f"{SIMS} simulations per league. Each team scores ~Normal(mean, sd) from its actual weekly points (blended with projections until 4 games), on the real remaining schedule. Ties broken by points-for.",
    }


# ── WEEKLY DIGEST ─────────────────────────────────────────────────────────────

LEVEL_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}

@router.post("/analysis/weekly-digest")
async def get_weekly_digest(req: UserRequest):
    """One Sunday-morning checklist: runs alerts, optimal lineup, waiver watch, playoff odds and
    the live matchup read, then ranks every league by urgency."""
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    week = req.week or current_week
    r = UserRequest(username=req.username, week=week)

    async def safe(name, coro):
        try:
            return name, await coro, None
        except Exception as ex:  # one broken feature must not kill the digest
            return name, None, f"{type(ex).__name__}: {ex}"

    parts = await asyncio.gather(
        safe("injured", get_injured_starters(r)),
        safe("questionable", get_questionable_starters(r)),
        safe("bye", get_starters_on_bye(r)),
        safe("open", get_open_starter_spots(r)),
        safe("zero", get_zero_projection_starters(r)),
        safe("optimal", get_optimal_lineup(r)),
        safe("waiver", get_waiver_watch(r)),
        safe("odds", get_playoff_odds(r)),
        safe("chance", get_theres_a_chance(r)),
    )
    data = {name: d for name, d, _ in parts}
    errors = [f"{name}: {err}" for name, _, err in parts if err]

    by_league = {}
    def L(name, team=None):
        if name not in by_league:
            by_league[name] = {"league": name, "team": team or "", "items": []}
        if team and not by_league[name]["team"]:
            by_league[name]["team"] = team
        return by_league[name]
    def add(league, team, level, kind, text, detail=None):
        L(league, team)["items"].append({"level": level, "type": kind, "text": text, "detail": detail})

    for x in (data.get("open") or {}).get("results", []):
        add(x["league"], x.get("team"), "CRITICAL", "open_slot", f"{x['open_slots']} empty starter slot{'s' if x['open_slots'] != 1 else ''}")
    for x in (data.get("injured") or {}).get("results", []):
        names = ", ".join(f"{p['name']} ({p['status']})" for p in x["injured"])
        add(x["league"], x.get("team"), "CRITICAL", "injured", f"{len(x['injured'])} OUT/IR starter{'s' if len(x['injured']) != 1 else ''}", names)
    for x in (data.get("bye") or {}).get("results", []):
        names = ", ".join(p["name"] for p in x["on_bye"])
        add(x["league"], x.get("team"), "CRITICAL", "bye", f"{len(x['on_bye'])} starter{'s' if len(x['on_bye']) != 1 else ''} on bye", names)
    for x in (data.get("zero") or {}).get("results", []):
        # skip bye / OUT-IR cases already counted above
        zs = [z for z in x["zero_starters"] if not (z.get("status") or "").lower().startswith("on bye")
              and not ((z.get("injury_status") or "").lower() in ("out", "ir", "pup", "sus", "na"))]
        if zs:
            add(x["league"], x.get("team"), "HIGH", "zero_proj", f"{len(zs)} starter{'s' if len(zs) != 1 else ''} projected for 0", ", ".join(f"{z['name']} — {z.get('status', '')}" for z in zs))
    for x in (data.get("questionable") or {}).get("results", []):
        add(x["league"], x.get("team"), "MEDIUM", "questionable", f"{len(x['questionable'])} questionable starter{'s' if len(x['questionable']) != 1 else ''}", ", ".join(p["name"] for p in x["questionable"]))
    for x in (data.get("optimal") or {}).get("results", []):
        lvl = "HIGH" if x["gain"] >= 5 else "MEDIUM"
        mv = "; ".join(f"{m['type'].upper()} {m['player']['name']}" + (f" → {m['to_slot']}" if m.get("to_slot") else "") for m in x["moves"][:4])
        add(x["league"], x.get("team"), lvl, "lineup", f"Lineup leaves {x['gain']} pts on the bench ({len(x['moves'])} move{'s' if len(x['moves']) != 1 else ''})", mv)
    for x in (data.get("waiver") or {}).get("results", []):
        if x["candidates"]:
            top = x["candidates"][0]
            lvl = "HIGH" if top["gain"] >= 5 else "MEDIUM"
            others = ", ".join(c["name"] for c in x["candidates"][1:3])
            add(x["league"], x.get("team"), lvl, "waiver",
                f"Waiver: {top['name']} ({top['position']}) +{top['gain']} over {top['replaces'].get('name') or 'empty slot'}",
                (f"Drop {top['drop_candidate']['name']}. " if top.get("drop_candidate") else "") + (f"Also: {others}" if others else ""))
    odds_by_league = {x["league"]: x for x in (data.get("odds") or {}).get("results", [])}
    for name, x in odds_by_league.items():
        ng = x.get("next_game") or {}
        if ng and ng.get("swing", 0) >= 20:
            add(name, x.get("team"), "HIGH", "must_win", f"Must-win vs {ng['opp_name']}: playoff odds {ng['playoff_if_win']}% if win, {ng['playoff_if_loss']}% if loss", f"Win prob {ng['win_prob']}%")
        add(name, x.get("team"), "INFO", "odds", f"{x['status']} — {x['playoff_pct']}% playoffs, {x['record']} (#{x['rank']}/{x['total_teams']})", x["advice"])
    for x in (data.get("chance") or {}).get("results", []):
        if x["status"] in ("COIN FLIP", "THERE'S A CHANCE", "LONG SHOT"):
            add(x["league"], x.get("team"), "INFO", "live", f"Live: {x['status']} ({x['win_prob']}%) — {x['my_live']} vs {x['opp_live']} ({x['my_left']} / {x['opp_left']} players left)")

    # Make sure every league appears, even with nothing to do
    for lg in leagues:
        L(lg["name"])
    for name, x in odds_by_league.items():
        L(name, x.get("team"))

    out = []
    for lg in by_league.values():
        lg["items"].sort(key=lambda i: LEVEL_RANK[i["level"]])
        actionable = [i for i in lg["items"] if i["level"] != "INFO"]
        lg["urgency"] = actionable[0]["level"] if actionable else "CLEAN"
        lg["action_count"] = len(actionable)
        o = odds_by_league.get(lg["league"])
        lg["playoff_pct"] = o["playoff_pct"] if o else None
        lg["record"] = o["record"] if o else None
        out.append(lg)
    # Keep Sleeper's league order (stable across runs) — with ~100 leagues, re-sorting by urgency
    # makes the list jump around week to week. Items inside a league are still ordered by level.
    order = {lg["name"]: i for i, lg in enumerate(leagues)}
    out.sort(key=lambda lg: order.get(lg["league"], 10**6))

    return {
        "week": week,
        "summary": {
            "leagues": len(out),
            "critical": sum(1 for lg in out if lg["urgency"] == "CRITICAL"),
            "high": sum(1 for lg in out if lg["urgency"] == "HIGH"),
            "medium": sum(1 for lg in out if lg["urgency"] == "MEDIUM"),
            "clean": sum(1 for lg in out if lg["urgency"] == "CLEAN"),
            "total_actions": sum(lg["action_count"] for lg in out),
        },
        "leagues": out,
        "errors": errors,
    }


# ── ROOTING GUIDE (FOR / AGAINST COUNTS) ──────────────────────────────────────

@router.post("/analysis/rooting-guide")
async def get_rooting_guide(req: UserRequest):
    """How many times each player starts FOR the user vs AGAINST the user (opponents' starters)
    across every league this week. Players still to play are listed first, then those already played."""
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week
    TOP = 50

    stats_array, schedule = await asyncio.gather(get_stats(season, week), get_schedule(season, week))
    stats_map = build_stats_map(stats_array)
    byes = (NFL_TEAMS - {t for g in schedule for t in (g.get("home"), g.get("away")) if t}) if schedule else set()
    # A team has played if any of its players has gp >= 1 this week (fallback when the schedule feed is down)
    teams_played = {(players_db.get(pid) or {}).get("team") for pid, st in stats_map.items() if (st.get("gp") or 0) >= 1}
    teams_played.discard(None)

    # Live game status per NFL team from Sleeper's schedule feed
    team_status = {}
    for g in schedule:
        st = (g.get("status") or "").lower()
        for t in (g.get("home"), g.get("away")):
            if t:
                team_status[t] = st
    have_schedule = bool(team_status)

    def game_state(pid, p):
        """'pre' | 'live' | 'final'"""
        team = p.get("team")
        st = team_status.get(team)
        if st in ("complete", "final", "post_game"):
            return "final"
        if st in ("in_game", "in_progress", "live", "halftime"):
            return "live"
        if st in ("pre_game", "scheduled"):
            return "pre"
        # No schedule info: fall back to whether anyone on the team has a game played
        if (stats_map.get(pid, {}).get("gp") or 0) >= 1 or team in teams_played:
            return "final" if have_schedule else "live"   # without the feed we can't tell live from final
        return "pre"

    tally = {}  # pid -> {"for": n, "against": n, "for_leagues": [], "against_leagues": []}
    def bump(pid, side, league_name):
        t = tally.setdefault(pid, {"for": 0, "against": 0, "for_leagues": [], "against_leagues": []})
        t[side] += 1
        t[side + "_leagues"].append(league_name)

    leagues_counted, no_matchup = 0, []
    all_rosters = await asyncio.gather(*[get_rosters(lg["league_id"]) for lg in leagues])
    all_matchups = await asyncio.gather(*[get_matchups(lg["league_id"], week) for lg in leagues])
    for league, rosters, matchups in zip(leagues, all_rosters, all_matchups):
        my_roster = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my_roster:
            continue
        my_m = next((m for m in matchups if m["roster_id"] == my_roster["roster_id"]), None)
        if not my_m or my_m.get("matchup_id") is None:
            no_matchup.append(league["name"])
            continue
        opp_m = next((m for m in matchups if m.get("matchup_id") == my_m["matchup_id"] and m["roster_id"] != my_roster["roster_id"]), None)
        leagues_counted += 1
        for pid in (my_m.get("starters") or []):
            if pid and str(pid) != "0":
                bump(str(pid), "for", league["name"])
        for pid in ((opp_m or {}).get("starters") or []):
            if pid and str(pid) != "0":
                bump(str(pid), "against", league["name"])

    rows = []
    for pid, t in tally.items():
        p = players_db.get(pid)
        if not p:
            continue
        net = t["for"] - t["against"]
        rows.append({
            "id": pid, "name": player_name(p), "position": p.get("position", "UNK"), "team": p.get("team") or "FA",
            "for": t["for"], "against": t["against"], "net": net, "total": t["for"] + t["against"],
            "state": game_state(pid, p),
            "played": game_state(pid, p) != "pre",
            "bye": is_on_bye(p, byes, week),
            "injury_status": p.get("injury_status"),
            "for_leagues": t["for_leagues"], "against_leagues": t["against_leagues"],
        })

    key = lambda r: (-abs(r["net"]), -r["total"], r["name"])
    remaining = sorted([r for r in rows if r["state"] == "pre" and not r["bye"]], key=key)
    live = sorted([r for r in rows if r["state"] == "live"], key=key)
    done = sorted([r for r in rows if r["state"] == "final"], key=key)
    on_bye = sorted([r for r in rows if r["bye"] and r["state"] == "pre"], key=key)

    # Game-level rollup for the games still to come: which NFL teams carry the most rooting interest
    by_team = {}
    for r in remaining + live:
        g = by_team.setdefault(r["team"], {"team": r["team"], "for": 0, "against": 0, "players": 0, "state": r["state"]})
        g["for"] += r["for"]; g["against"] += r["against"]; g["players"] += 1
    games = sorted(by_team.values(), key=lambda g: (0 if g["state"] == "live" else 1, -(g["for"] + g["against"])))
    for g in games:
        g["net"] = g["for"] - g["against"]

    return {
        "week": week,
        "summary": {
            "leagues": leagues_counted, "no_matchup": no_matchup,
            "players_remaining": len(remaining), "players_live": len(live), "players_played": len(done), "players_on_bye": len(on_bye),
            "have_schedule": have_schedule,
            "unique_players": len(rows),
            "biggest_for": remaining[0] if remaining and remaining[0]["net"] > 0 else next((r for r in remaining if r["net"] > 0), None),
            "biggest_against": next((r for r in remaining if r["net"] < 0), None),
        },
        "remaining": remaining[:TOP], "remaining_total": len(remaining),
        "live": live[:TOP], "live_total": len(live),
        "played": done[:TOP], "played_total": len(done),
        "on_bye": on_bye[:TOP],
        "teams_remaining": games,
        "note": "Counts starters only (your lineup = FOR, opponent's lineup = AGAINST). Net = FOR − AGAINST; sorted by |net|. "
                "Game state comes from Sleeper's live schedule feed (pre-game / in progress / final).",
    }


# ── SEASON RECORDS (record / PF / PA / max PF per league) ─────────────────────

def _fpts(st, key):
    return round((st.get(key) or 0) + (st.get(key + "_decimal") or 0) / 100.0, 2)


@router.post("/analysis/season-records")
async def get_season_records(req: UserRequest):
    """One row per league: the user's team name, record, season points for, points against and
    max points for (Sleeper's 'ppts' = points with a perfect lineup every week)."""
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]

    all_rosters, all_users = await asyncio.gather(
        asyncio.gather(*[get_rosters(lg["league_id"]) for lg in leagues]),
        asyncio.gather(*[get_league_users(lg["league_id"]) for lg in leagues]),
    )
    rows = []
    for league, rosters, league_users in zip(leagues, all_rosters, all_users):
        my = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my:
            continue
        st = my.get("settings") or {}
        mu = next((u for u in league_users if u["user_id"] == user_id), None)
        team = (mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")
        w, l, t = st.get("wins", 0), st.get("losses", 0), st.get("ties", 0)
        gp = w + l + t
        pf, pa, maxpf = _fpts(st, "fpts"), _fpts(st, "fpts_against"), _fpts(st, "ppts")
        # rank in league by wins then PF (Sleeper's default standings)
        order = sorted(rosters, key=lambda r: (-(r.get("settings") or {}).get("wins", 0), -_fpts(r.get("settings") or {}, "fpts")))
        rank = next((i + 1 for i, r in enumerate(order) if r["roster_id"] == my["roster_id"]), None)
        rows.append({
            "league": league["name"], "team": team,
            "record": f"{w}-{l}" + (f"-{t}" if t else ""), "wins": w, "losses": l, "ties": t,
            "win_pct": round((w + 0.5 * t) / gp, 3) if gp else 0.0,
            "pf": pf, "pa": pa, "max_pf": maxpf,
            "pf_per_game": round(pf / gp, 1) if gp else 0.0,
            "pa_per_game": round(pa / gp, 1) if gp else 0.0,
            "diff": round(pf - pa, 2),
            "efficiency": round(100 * pf / maxpf, 1) if maxpf else None,
            "left_on_bench": round(maxpf - pf, 2) if maxpf else None,
            "rank": rank, "total_teams": len(rosters),
        })

    n = len(rows)
    tot_w = sum(r["wins"] for r in rows); tot_l = sum(r["losses"] for r in rows); tot_t = sum(r["ties"] for r in rows)
    effs = [r["efficiency"] for r in rows if r["efficiency"] is not None]
    return {
        "season": season, "week": current_week,
        "summary": {
            "leagues": n, "record": f"{tot_w}-{tot_l}" + (f"-{tot_t}" if tot_t else ""),
            "win_pct": round((tot_w + 0.5 * tot_t) / max(tot_w + tot_l + tot_t, 1), 3),
            "pf": round(sum(r["pf"] for r in rows), 1), "pa": round(sum(r["pa"] for r in rows), 1),
            "max_pf": round(sum(r["max_pf"] for r in rows), 1),
            "avg_efficiency": round(sum(effs) / len(effs), 1) if effs else None,
            "best_eff": max(rows, key=lambda r: r["efficiency"] or 0)["league"] if effs else None,
            "worst_eff": min(rows, key=lambda r: r["efficiency"] if r["efficiency"] is not None else 999)["league"] if effs else None,
        },
        "results": rows,
        "note": "Max PF is Sleeper's potential points (best possible lineup each week). Efficiency = PF ÷ Max PF. Rows are in your Sleeper league order.",
    }


# ── IR-ELIGIBLE PLAYERS NOT ON IR ─────────────────────────────────────────────

@router.post("/alerts/ir-eligible")
async def get_ir_eligible(req: UserRequest):
    """Rostered players (starters or bench; taxi ignored) whose injury status qualifies for the league's
    IR slot but who are not in the reserve (IR) slot. Respects each league's reserve_allow_* settings."""
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    results = []

    all_rosters, all_users = await asyncio.gather(
        asyncio.gather(*[get_rosters(lg["league_id"]) for lg in leagues]),
        asyncio.gather(*[get_league_users(lg["league_id"]) for lg in leagues]),
    )
    for league, rosters, league_users in zip(leagues, all_rosters, all_users):
        my = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my:
            continue
        settings = league.get("settings") or {}
        ir_slots = max(int(settings.get("reserve_slots") or 0), sum(1 for x in (league.get("roster_positions") or []) if x == "IR"))
        # Statuses this league lets you stash on IR (Sleeper defaults: IR and PUP only)
        allowed = {"IR", "PUP"}
        if settings.get("reserve_allow_out"):      allowed.add("OUT")
        if settings.get("reserve_allow_doubtful"): allowed.add("DOUBTFUL")
        if settings.get("reserve_allow_sus"):      allowed.add("SUS")
        if settings.get("reserve_allow_na"):       allowed.add("NA")
        if settings.get("reserve_allow_cov"):      allowed.add("COV")

        reserve = {str(x) for x in (my.get("reserve") or [])}
        starters = {str(x) for x in (my.get("starters") or [])}
        taxi = {str(x) for x in (my.get("taxi") or [])}
        mu = next((u for u in league_users if u["user_id"] == user_id), None)
        team = (mu or {}).get("metadata", {}).get("team_name") or user.get("display_name", "")

        flagged, not_eligible = [], []
        for pid in (my.get("players") or []):
            pid = str(pid)
            if pid in reserve or pid in taxi:
                continue  # already on IR, or taxi (taxi players aren't costing a roster spot)
            p = players_db.get(pid)
            if not p:
                continue
            st = (p.get("injury_status") or "").upper()
            if st not in ("OUT", "IR", "PUP", "SUS", "NA", "COV", "DOUBTFUL"):
                continue
            if st == "DOUBTFUL" and "DOUBTFUL" not in allowed:
                continue  # doubtful is only interesting when the league allows it on IR
            row = {"id": pid, "name": player_name(p), "position": p.get("position"), "team": p.get("team") or "FA",
                   "status": st, "role": "starter" if pid in starters else "bench",
                   "injury": p.get("injury_body_part") or p.get("injury_notes") or None}
            (flagged if st in allowed else not_eligible).append(row)

        if not flagged and not not_eligible:
            continue
        open_ir = max(ir_slots - len(reserve), 0)
        results.append({
            "league": league["name"], "team": team,
            "ir_slots": ir_slots, "ir_used": len(reserve), "ir_open": open_ir,
            "allowed_statuses": sorted(allowed),
            "eligible": sorted(flagged, key=lambda r: (r["role"] != "starter", r["name"])),
            "not_eligible": sorted(not_eligible, key=lambda r: (r["role"] != "starter", r["name"])),
            "action": ("No IR slot in this league — drop or hold." if ir_slots == 0
                       else f"Move {min(len(flagged), open_ir)} to IR now ({open_ir} open)." if flagged and open_ir > 0
                       else "IR is full — swap someone out or drop." if flagged
                       else "Out this week but not IR-eligible here."),
        })

    n_elig = sum(len(r["eligible"]) for r in results)
    return {
        "results": results,
        "summary": {
            "leagues": len(results),
            "eligible_players": n_elig,
            "can_move_now": sum(min(len(r["eligible"]), r["ir_open"]) for r in results),
            "ir_full": sum(1 for r in results if r["eligible"] and r["ir_slots"] > 0 and r["ir_open"] == 0),
            "no_ir_slot": sum(1 for r in results if r["eligible"] and r["ir_slots"] == 0),
            "not_eligible_players": sum(len(r["not_eligible"]) for r in results),
        },
        "note": "Eligibility uses each league's IR rules (Sleeper default: IR and PUP only; some leagues also allow OUT, SUS, NA, COV or Doubtful). "
                "'Not eligible' lists OUT/other players the league won't let you stash, so you can decide to hold or drop.",
    }


# ── POWER RANKINGS (all my teams, best → worst) ──────────────────────────────

@router.post("/analysis/power-rankings")
async def get_power_rankings(req: UserRequest):
    """Every league's team ordered by how it is performing: a blend of record (win %, with a
    points-based adjustment so 'lucky' records don't over-rank) and roster rating (Juggernaut → Rebuild)."""
    user, season, current_week, evals = await _evaluate_all(req.username, req.week)
    rows = []
    for league, team, ev in evals:
        gp = ev["games_played"]
        # Record component: win% blended toward points-based expected win% early in the season
        pyth = ev.get("pyth_win_pct")
        if pyth is None and ev["fpts"] > 0 and ev["fpa"] > 0:
            pyth = ev["fpts"] ** 2.37 / (ev["fpts"] ** 2.37 + ev["fpa"] ** 2.37)
        rec_pct = ev["win_pct"] if gp else 0.5
        if pyth is not None and gp:
            w = min(gp / 6.0, 1.0)             # trust the raw record fully after ~6 games
            rec_pct = w * ev["win_pct"] + (1 - w) * (0.5 * ev["win_pct"] + 0.5 * pyth)
        record_score = 100 * rec_pct
        roster_score = 100 * (ev["roster_composite"] - 1) / 4      # composite runs 1..5 → 0..100
        standing_score = 100 * (1 - (ev["rank"] - 1) / max(ev["total_teams"] - 1, 1))
        if gp == 0:
            score = roster_score
        else:
            score = 0.5 * record_score + 0.35 * roster_score + 0.15 * standing_score
        rows.append({
            "league": league["name"], "team": team,
            "record": f"{ev['wins']}-{ev['losses']}" + (f"-{ev['ties']}" if ev["ties"] else ""),
            "win_pct": round(ev["win_pct"], 3), "games_played": gp,
            "rank": ev["rank"], "total_teams": ev["total_teams"], "in_playoffs": ev["in_playoffs"],
            "tier": ev["roster_tier"], "tier_color": ev["roster_tier_color"], "tier_icon": ev["roster_tier_icon"],
            "roster_composite": ev["roster_composite"], "blended_tier": ev["tier"],
            "pf": round(ev["fpts"], 1), "pa": round(ev["fpa"], 1), "pts_vs_avg": ev["pts_vs_avg"],
            "score": round(score, 1), "record_score": round(record_score, 1), "roster_score": round(roster_score, 1),
            "standing_score": round(standing_score, 1),
        })
    rows.sort(key=lambda r: (-r["score"], -r["win_pct"], -r["roster_composite"], r["league"]))
    for i, r in enumerate(rows, start=1):
        r["power_rank"] = i
    n = len(rows)
    tiers = {}
    for r in rows:
        tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1
    return {
        "week": current_week,
        "summary": {
            "leagues": n,
            "top": rows[0] if rows else None, "bottom": rows[-1] if rows else None,
            "avg_score": round(sum(r["score"] for r in rows) / n, 1) if n else 0,
            "tiers": tiers,
            "above_500": sum(1 for r in rows if r["win_pct"] > 0.5),
            "in_playoff_spot": sum(1 for r in rows if r["in_playoffs"]),
        },
        "results": rows,
        "note": "Score = 50% record (win %, nudged toward points-based expectation early in the year) + 35% roster rating "
                "(Juggernaut → Rebuild composite) + 15% league standing. Before week 1 it is roster rating only.",
    }


# ── PLAYER LOOKUP (where do I own him, starting or benched?) ─────────────────

@router.post("/analysis/player-lookup")
async def get_player_lookup(req: UserPlayerRequest):
    """Find a player by name and list every league where the user rosters him, with his role this
    week (starter slot / bench / IR / taxi), plus leagues where this week's opponent starts him."""
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week
    q = " ".join((req.player_name or "").lower().split())
    if not q:
        raise HTTPException(status_code=400, detail="Enter a player name.")

    # Match: exact full name first, then substring on full/last name; prefer active players on a team
    POS = ALL_POS_SET
    def nm(p): return player_name(p).lower()
    exact = [(pid, p) for pid, p in players_db.items() if p.get("position") in POS and nm(p) == q]
    cands = exact or [(pid, p) for pid, p in players_db.items() if p.get("position") in POS and (q in nm(p) or q == (p.get("last_name") or "").lower())]
    cands.sort(key=lambda t: (not t[1].get("team"), (t[1].get("status") or "") != "Active", nm(t[1])))
    if not cands:
        raise HTTPException(status_code=404, detail=f"No player matching '{req.player_name}'.")
    active = [c for c in cands if c[1].get("team")] or cands
    if len(active) > 1 and not exact:
        return {"ambiguous": True, "query": req.player_name,
                "matches": [{"id": pid, "name": player_name(p), "position": p.get("position"), "team": p.get("team") or "FA"} for pid, p in active[:12]],
                "note": "Several players match — type the full name."}
    pid, p = active[0]
    player = {"id": pid, "name": player_name(p), "position": p.get("position"), "team": p.get("team") or "FA",
              "injury_status": p.get("injury_status"), "age": p.get("age"), "years_exp": p.get("years_exp")}

    all_rosters, all_users, all_matchups = await asyncio.gather(
        asyncio.gather(*[get_rosters(lg["league_id"]) for lg in leagues]),
        asyncio.gather(*[get_league_users(lg["league_id"]) for lg in leagues]),
        asyncio.gather(*[get_matchups(lg["league_id"], week) for lg in leagues]),
    )
    owned, against, elsewhere, available = [], [], [], []
    for league, rosters, league_users, matchups in zip(leagues, all_rosters, all_users, all_matchups):
        my = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my:
            continue
        users = {u["user_id"]: u for u in league_users}
        tname = lambda r: (users.get(r.get("owner_id")) or {}).get("metadata", {}).get("team_name") or (users.get(r.get("owner_id")) or {}).get("display_name") or f"Team {r['roster_id']}"
        holder = next((r for r in rosters if pid in {str(x) for x in (r.get("players") or [])}), None)
        my_m = next((m for m in matchups if m["roster_id"] == my["roster_id"]), None)
        if holder is None:
            available.append({"league": league["name"], "team": tname(my)})
            continue
        if holder["roster_id"] == my["roster_id"]:
            starters = [str(x) for x in ((my_m or my).get("starters") or [])]
            slots = [x for x in league.get("roster_positions", []) if x not in ("BN", "IR", "TAXI")]
            if pid in {str(x) for x in (my.get("reserve") or [])}:
                role, slot = "IR", None
            elif pid in {str(x) for x in (my.get("taxi") or [])}:
                role, slot = "TAXI", None
            elif pid in starters:
                i = starters.index(pid); role, slot = "STARTER", (slots[i] if i < len(slots) else "?")
            else:
                role, slot = "BENCH", None
            owned.append({"league": league["name"], "team": tname(my), "role": role, "slot": slot,
                          "pts": float(((my_m or {}).get("players_points") or {}).get(pid, 0) or 0)})
        else:
            opp_m = next((m for m in matchups if my_m and m.get("matchup_id") == my_m.get("matchup_id") and m["roster_id"] != my["roster_id"]), None)
            is_opp = bool(opp_m and opp_m["roster_id"] == holder["roster_id"])
            starts = pid in {str(x) for x in ((opp_m or holder).get("starters") or [])}
            row = {"league": league["name"], "team": tname(my), "owner": tname(holder), "starting": starts}
            (against if is_opp else elsewhere).append(row)

    role_order = {"STARTER": 0, "BENCH": 1, "TAXI": 2, "IR": 3}
    owned.sort(key=lambda r: (role_order[r["role"]], r["league"]))
    return {
        "week": week, "player": player,
        "summary": {"leagues": len(leagues), "owned": len(owned),
                    "starting": sum(1 for r in owned if r["role"] == "STARTER"),
                    "bench": sum(1 for r in owned if r["role"] == "BENCH"),
                    "taxi": sum(1 for r in owned if r["role"] == "TAXI"),
                    "ir": sum(1 for r in owned if r["role"] == "IR"),
                    "against": len(against), "available": len(available), "elsewhere": len(elsewhere)},
        "owned": owned, "against": against, "available": available, "elsewhere": elsewhere,
    }


# ── TRADE FINDER (acquire a specific player) ──────────────────────────────────

def _age_mult(pos, age, superflex):
    """Dynasty age curve per position. Returns a multiplier on per-game production."""
    a = age or 27
    if pos == "RB":
        m = 1.15 if a <= 24 else 1.0 if a <= 26 else 0.85 if a == 27 else 0.7 if a == 28 else 0.55 if a == 29 else 0.4
    elif pos == "WR":
        m = 1.15 if a <= 24 else 1.0 if a <= 28 else 0.9 if a == 29 else 0.8 if a == 30 else 0.65 if a == 31 else 0.5
    elif pos == "TE":
        m = 1.1 if a <= 25 else 1.0 if a <= 29 else 0.85 if a == 30 else 0.7
    elif pos == "QB":
        m = 1.1 if a <= 26 else 1.0 if a <= 32 else 0.85 if a <= 35 else 0.65
        if superflex:
            m *= 1.3
    elif pos in ("DL", "LB", "DB"):
        m = 1.05 if a <= 25 else 1.0 if a <= 28 else 0.85 if a <= 30 else 0.65
    else:
        m = 0.3   # K / DEF carry little dynasty value
    return m


def _dyn_value(ppg, pos, age, superflex):
    """Dynasty trade value: production × age curve, convexed so studs > two average players."""
    base = max(ppg, 0) * _age_mult(pos, age, superflex)
    return round(base ** 1.3, 1)


def _owned_picks(roster_id, rosters, traded_picks, season, draft_rounds, seasons_ahead=2):
    """Future picks a roster holds: its own unless traded away, plus any acquired."""
    picks = []
    for yr in range(1, seasons_ahead + 1):
        yr_s = str(int(season) + yr)
        for rnd in range(1, draft_rounds + 1):
            for r in rosters:
                orig = r["roster_id"]
                owner = orig
                for tp in traded_picks:
                    if str(tp.get("season")) == yr_s and tp.get("round") == rnd and tp.get("roster_id") == orig:
                        owner = tp.get("owner_id")
                if owner == roster_id:
                    picks.append({"season": yr_s, "round": rnd, "original_roster": orig, "years_out": yr})
    return picks


@router.post("/analysis/trade-finder")
async def get_trade_finder(req: UserPlayerRequest):
    """For every league where another manager owns the named player, build two trade offers from the
    user's assets (players + future picks, up to 4-for-1) that the other side would plausibly accept:
    value parity with a premium, aimed at their roster needs and their contender/rebuild posture."""
    user, nfl_state, season, current_week, leagues, players_db = await get_user_context(req.username)
    user_id = user["user_id"]
    week = req.week or current_week
    weeks_completed = max(0, min(week - 1, current_week - 1))
    PROTECT = 3
    MAX_ASSETS = 4

    q = " ".join((req.player_name or "").lower().split())
    if not q:
        raise HTTPException(status_code=400, detail="Enter a player name.")
    POS = ALL_POS_SET
    nm = lambda p: player_name(p).lower()
    exact = [(pid, p) for pid, p in players_db.items() if p.get("position") in POS and nm(p) == q]
    cands = exact or [(pid, p) for pid, p in players_db.items() if p.get("position") in POS and (q in nm(p) or q == (p.get("last_name") or "").lower())]
    cands.sort(key=lambda t: (not t[1].get("team"), (t[1].get("status") or "") != "Active", nm(t[1])))
    if not cands:
        raise HTTPException(status_code=404, detail=f"No player matching '{req.player_name}'.")
    active = [c for c in cands if c[1].get("team")] or cands
    if len(active) > 1 and not exact:
        return {"ambiguous": True, "query": req.player_name,
                "matches": [{"id": pid, "name": player_name(p), "position": p.get("position"), "team": p.get("team") or "FA"} for pid, p in active[:12]]}
    tpid, tp = active[0]
    target = {"id": tpid, "name": player_name(tp), "position": tp.get("position"), "team": tp.get("team") or "FA",
              "age": tp.get("age"), "injury_status": tp.get("injury_status")}

    proj_array, weekly_by_player = await asyncio.gather(get_projections(season, week), _weekly_stats_by_player(season, weeks_completed))
    all_rosters, all_users, all_traded = await asyncio.gather(
        asyncio.gather(*[get_rosters(lg["league_id"]) for lg in leagues]),
        asyncio.gather(*[get_league_users(lg["league_id"]) for lg in leagues]),
        asyncio.gather(*[get_traded_picks(lg["league_id"]) for lg in leagues]),
    )

    results, no_offer, free_agent, mine = [], [], [], []
    for league, rosters, league_users, traded in zip(leagues, all_rosters, all_users, all_traded):
        my = next((r for r in rosters if r["owner_id"] == user_id), None)
        if not my:
            continue
        users = {u["user_id"]: u for u in league_users}
        tname = lambda r: (users.get(r.get("owner_id")) or {}).get("metadata", {}).get("team_name") or (users.get(r.get("owner_id")) or {}).get("display_name") or f"Team {r['roster_id']}"
        holder = next((r for r in rosters if tpid in {str(x) for x in (r.get("players") or [])}), None)
        if holder is None:
            free_agent.append({"league": league["name"], "team": tname(my)}); continue
        if holder["roster_id"] == my["roster_id"]:
            mine.append({"league": league["name"], "team": tname(my)}); continue

        ss = league.get("scoring_settings") or {}
        proj_map = build_proj_map(proj_array, ss)
        slots = [x for x in league.get("roster_positions", []) if x not in ("BN", "IR", "TAXI")]
        superflex = "SUPER_FLEX" in slots
        draft_rounds = int((league.get("settings") or {}).get("draft_rounds") or 4)

        def ppg(pid):
            avg, sd, gp, _ = _season_line(weekly_by_player.get(pid), ss)
            proj = proj_map.get(pid, 0)
            return 0.5 * proj + 0.5 * avg if gp >= 2 else proj
        def pl(pid):
            p = players_db.get(pid)
            if not p or p.get("position") not in POS:
                return None
            v = _dyn_value(ppg(pid), p["position"], p.get("age"), superflex)
            return {"type": "player", "id": pid, "name": player_name(p), "position": p["position"], "team": p.get("team") or "FA",
                    "age": p.get("age"), "ppg": round(ppg(pid), 1), "value": v, "injury_status": p.get("injury_status")}

        # League-wide value distribution → pick values + position baselines
        all_vals = sorted([x["value"] for r in rosters for pid in (r.get("players") or []) if (x := pl(str(pid)))], reverse=True)
        def pct(pq):
            if not all_vals: return 0
            return all_vals[min(int(len(all_vals) * (1 - pq)), len(all_vals) - 1)]
        pick_val = {1: pct(0.80), 2: pct(0.55), 3: pct(0.35), 4: pct(0.20)}
        def pick_value(pk):
            base = pick_val.get(pk["round"], pct(0.1))
            return round(base * (0.85 ** (pk["years_out"] - 1)), 1)

        # Their side: tier, needs, their lineup value at each position
        their_ev = _evaluate_league(league, holder, rosters, traded, players_db, proj_map, season, current_week)
        their_players = [x for pid in (holder.get("players") or []) if (x := pl(str(pid)))]
        their_players.sort(key=lambda x: -x["value"])
        tgt = next((x for x in their_players if x["id"] == tpid), None) or pl(tpid)
        target_value = tgt["value"]
        their_top3 = {x["id"] for x in their_players[:3]}
        # position needs: how many startable they have vs how many they need to start
        def pos_demand(pos):
            ded = sum(1 for sl in slots if sl == pos)
            flex = sum(1 / len(SLOT_ELIGIBILITY[sl]) for sl in slots if sl in SLOT_ELIGIBILITY and len(SLOT_ELIGIBILITY[sl]) > 1 and pos in SLOT_ELIGIBILITY[sl] and sl != "SUPER_FLEX")
            if pos == "QB" and superflex: flex += 1.0
            return ded + int(flex + 0.5)
        lg_pos_vals = {}
        for r in rosters:
            for pid in (r.get("players") or []):
                x = pl(str(pid))
                if x: lg_pos_vals.setdefault(x["position"], []).append(x["value"])
        def startable_cut(pos):  # value of the Nth best at that position league-wide, N = teams × demand
            vals = sorted(lg_pos_vals.get(pos, []), reverse=True)
            n = max(len(rosters) * max(pos_demand(pos), 1) - 1, 0)
            return vals[min(n, len(vals) - 1)] if vals else 0
        def need_of(roster_players, pos, exclude=set()):
            have = sum(1 for x in roster_players if x["position"] == pos and x["id"] not in exclude and x["value"] >= startable_cut(pos))
            return pos_demand(pos) - have      # >0 short, <0 surplus
        tf_pos = [x for x in ("QB", "RB", "WR", "TE") + IDP_POS if x in league_positions(league)]
        their_need = {pos: need_of(their_players, pos, exclude={tpid}) for pos in tf_pos}
        rebuild = their_ev["roster_tier"] in ("Rebuild", "Fringe")
        contender = their_ev["roster_tier"] in ("Juggernaut", "Contender")

        # My side: assets
        my_players = [x for pid in (my.get("players") or []) if (x := pl(str(pid))) and x["position"] in tf_pos]
        my_players.sort(key=lambda x: -x["value"])
        protected = {x["id"] for x in my_players[:PROTECT]}
        tgt_v_for_pool = (next((x for x in their_players if x["id"] == tpid), None) or pl(tpid))["value"]
        # candidates closest in value to the target (so cheap targets get cheap offers), not just my best players
        tradeable = sorted([x for x in my_players if x["id"] not in protected and (x["injury_status"] or "").upper() not in ("IR", "PUP", "OUT")],
                           key=lambda x: abs(x["value"] - tgt_v_for_pool))[:14]
        my_picks = [{"type": "pick", "id": f"pick-{pk['season']}-{pk['round']}-{pk['original_roster']}",
                     "name": f"{pk['season']} Round {pk['round']}" + ("" if pk["original_roster"] == my["roster_id"] else f" (via {tname(next(r for r in rosters if r['roster_id'] == pk['original_roster']))})"),
                     "round": pk["round"], "season": pk["season"], "years_out": pk["years_out"], "value": pick_value(pk)}
                    for pk in _owned_picks(my["roster_id"], rosters, traded, season, min(draft_rounds, 4))]
        my_picks.sort(key=lambda x: -x["value"])
        my_picks = my_picks[:6]
        my_need_after = lambda sent_ids: {pos: need_of(my_players, pos, exclude=sent_ids) for pos in tf_pos}
        my_need_before = my_need_after(set())

        premium = 1.05 + (0.10 if tpid in their_top3 else 0) - (0.03 if their_need.get(target["position"], 0) < 0 else 0)
        lo, hi = target_value * premium, target_value * premium * 1.18

        from itertools import combinations
        assets = [a for a in tradeable if a["value"] >= 1.0] + my_picks   # no zero-value throw-ins
        offers = []
        for k in range(1, MAX_ASSETS + 1):
            for combo in combinations(assets, k):
                sv = sum(a["value"] for a in combo)
                if sv < lo * 0.97 or sv > hi * 1.05:
                    continue
                players_sent = [a for a in combo if a["type"] == "player"]
                picks_sent = [a for a in combo if a["type"] == "pick"]
                # quality rule: no quantity-for-quality dumps — best piece ≥ 45% of target (picks-only exempt for rebuilders)
                best_piece = max(a["value"] for a in combo)
                if players_sent and best_piece < 0.45 * target_value:
                    continue
                if not players_sent and not rebuild and k > 2:
                    continue
                # my lineup rule: don't drop below demand at any position (target joins my roster)
                sent_ids = {a["id"] for a in players_sent}
                after = my_need_after(sent_ids)
                after[target["position"]] = after.get(target["position"], 0) - (1 if tgt["value"] >= startable_cut(target["position"]) else 0)
                # the trade must not make any position shortage worse than it already is
                if any(after[pos] > max(my_need_before[pos], 0) for pos in after):
                    continue
                # fit score
                fit = 0.0
                for a in players_sent:
                    n = their_need.get(a["position"], 0)
                    fit += 1.0 if n > 0 else -0.6 if n < -1 else 0.1
                    if contender and a["value"] >= startable_cut(a["position"]): fit += 0.4
                    if rebuild and (a["age"] or 30) <= 25: fit += 0.4
                    if rebuild and (a["age"] or 0) >= 28: fit -= 0.5
                for a in picks_sent:
                    fit += (0.9 if rebuild else 0.2 if contender else 0.5) * (1.2 if a["round"] == 1 else 0.8)
                parity = sv / target_value
                over = max(parity - premium, 0)
                score = fit - 1.5 * over - 0.25 * (k - 1) + (0.3 if lo <= sv <= hi else 0)
                offers.append({"assets": list(combo), "send_value": round(sv, 1), "ratio": round(parity, 2), "fit": round(fit, 2),
                               "score": round(score, 2), "has_pick": bool(picks_sent), "n": k})
        if not offers:
            no_offer.append({"league": league["name"], "team": tname(my), "owner": tname(holder), "target_value": target_value,
                             "reason": "can't reach value without touching your protected top 3" if tradeable or my_picks else "no tradeable assets"})
            continue
        offers.sort(key=lambda o: -o["score"])
        o1 = offers[0]
        # second offer: a different shape — include a pick if the first didn't (or vice-versa), else next-best distinct set
        ids1 = {a["id"] for a in o1["assets"]}
        distinct = [o for o in offers if not ids1 <= {a["id"] for a in o["assets"]} and not {a["id"] for a in o["assets"]} <= ids1]
        alt = [o for o in distinct if o["has_pick"] != o1["has_pick"]] or distinct
        o2 = alt[0] if alt else None
        def why(o):
            bits = []
            needs = [a["position"] for a in o["assets"] if a["type"] == "player" and their_need.get(a["position"], 0) > 0]
            if needs: bits.append(f"fills their {'/'.join(sorted(set(needs)))} need")
            if any(a["type"] == "pick" for a in o["assets"]): bits.append("picks suit a rebuilder" if rebuild else "pick sweetener")
            bits.append(f"{int(round(o['ratio'] * 100))}% of his value")
            return " · ".join(bits)
        def grade(o):
            return "A" if o["score"] >= 2.0 else "B" if o["score"] >= 1.0 else "C" if o["score"] >= 0.3 else "D"
        fmt = lambda o: o and {**o, "why": why(o), "grade": grade(o)}
        results.append({
            "league": league["name"], "team": tname(my), "owner": tname(holder),
            "owner_tier": their_ev["roster_tier"], "owner_tier_color": their_ev["roster_tier_color"], "owner_record": f"{their_ev['wins']}-{their_ev['losses']}",
            "target_value": target_value, "target_ppg": tgt["ppg"], "target_is_their_top3": tpid in their_top3,
            "their_need_at_pos": their_need.get(target["position"], 0), "superflex": superflex,
            "premium": round(premium, 2), "ask_range": [round(lo, 1), round(hi, 1)],
            "offers": [fmt(o1)] + ([fmt(o2)] if o2 else []),
            "protected": [x["name"] for x in my_players[:PROTECT]],
            "feasibility": o1["score"],
        })

    results.sort(key=lambda r: -r["feasibility"])
    return {
        "week": week, "player": target,
        "summary": {"leagues": len(leagues), "offers_built": len(results), "no_offer": len(no_offer), "free_agent": len(free_agent), "already_mine": len(mine),
                    "a_grade": sum(1 for r in results if r["offers"][0]["grade"] == "A")},
        "results": results, "no_offer": no_offer, "free_agent": free_agent, "mine": mine,
        "note": "Values = league-scored per-game production × a dynasty age curve (QBs boosted in superflex), convexed so stars outweigh depth. "
                "Picks are priced off that league's player value distribution (1st ≈ 80th percentile player, discounted 15%/yr out). "
                "Offers send 105–120%+ of his value (more if he's their top-3), favor positions they're short at, respect your top-3 protect list, "
                "never leave you short at a position, and cap at 4-for-1.",
    }


# ── HAIL MARY (games still in doubt + what it takes) ──────────────────────────

@router.post("/analysis/hail-mary")
async def get_hail_mary(req: UserRequest):
    """Only matchups that are genuinely still in doubt (10–90% win probability, players left to play).
    For each: points you need from your remaining players, scaled per player by projection, and what
    the opponent's remaining players must be held under."""
    LOW, HIGH = 10.0, 90.0
    base = await get_theres_a_chance(req)
    results, ignored_win, ignored_loss = [], [], []

    for r in base["results"]:
        if r["my_left"] + r["opp_left"] == 0:
            continue
        if r["win_prob"] > HIGH:
            ignored_win.append({"league": r["league"], "win_prob": r["win_prob"]}); continue
        if r["win_prob"] < LOW:
            ignored_loss.append({"league": r["league"], "win_prob": r["win_prob"]}); continue

        my_need = round(max(r["opp_exp"] - r["my_live"], 0), 1)       # to pass their expected final
        their_need = round(max(r["my_exp"] - r["opp_live"], 0), 1)    # what they need to pass yours
        my_rem, opp_rem = r["my_remaining_proj"], r["opp_remaining_proj"]

        def per_player(rows_pre, rows_live, total_needed, total_proj):
            scale = (total_needed / total_proj) if total_proj > 0 else None
            out = []
            for p in rows_live + rows_pre:
                proj = p.get("remaining_proj", p.get("proj_pts", 0)) or 0
                out.append({**p, "rem_proj": round(proj, 1),
                            "needs": round(proj * scale, 1) if scale is not None else None})
            return sorted(out, key=lambda x: -x["rem_proj"])

        mine = per_player(r["my_remaining"], r["my_in_progress"], my_need, my_rem)
        theirs = per_player(r["opp_remaining"], r["opp_in_progress"], their_need, opp_rem)

        if r["my_left"] == 0:
            situation, headline = "SWEAT IT OUT", f"You're done at {r['my_live']}. Their {r['opp_left']} remaining must score under {round(r['my_live'] - r['opp_live'], 1)} (projected {opp_rem})."
        elif r["opp_left"] == 0:
            situation, headline = "YOUR MOVE", f"They're done at {r['opp_live']}. You need {round(max(r['opp_live'] - r['my_live'], 0) + 0.01, 1)} from {r['my_left']} player{'s' if r['my_left'] != 1 else ''} (projected {my_rem})."
        elif r["my_live"] >= r["opp_live"] and r["win_prob"] >= 50:
            situation, headline = "HOLD ON", f"Ahead {r['my_live']}–{r['opp_live']}. Their {r['opp_left']} need {their_need} (projected {opp_rem}) to pass your expected {r['my_exp']}."
        elif my_need > my_rem * 1.15:
            situation, headline = "HAIL MARY", f"Need {my_need} from {r['my_left']} player{'s' if r['my_left'] != 1 else ''} — {int(round(100 * my_need / my_rem)) if my_rem else '∞'}% of their projection."
        else:
            situation, headline = "IN REACH", f"Need {my_need} from {r['my_left']} player{'s' if r['my_left'] != 1 else ''}, projected {my_rem}."

        pace = round(100 * my_need / my_rem) if my_rem > 0 and r["my_left"] > 0 else None
        results.append({
            "league": r["league"], "team": r["team"], "opp_name": r["opp_name"],
            "win_prob": r["win_prob"], "situation": situation, "headline": headline,
            "my_live": r["my_live"], "opp_live": r["opp_live"], "my_exp": r["my_exp"], "opp_exp": r["opp_exp"],
            "my_left": r["my_left"], "opp_left": r["opp_left"],
            "my_need": my_need, "my_remaining_proj": my_rem, "pace_pct": pace,
            "their_need": their_need, "opp_remaining_proj": opp_rem,
            "hold_under": round(r["my_live"] - r["opp_live"], 1) if r["my_left"] == 0 else None,
            "my_players": mine, "their_players": theirs,
        })

    results.sort(key=lambda x: abs(x["win_prob"] - 50))
    return {
        "week": base["week"], "have_schedule": base["have_schedule"],
        "summary": {
            "in_doubt": len(results),
            "favored": sum(1 for x in results if x["win_prob"] >= 50),
            "underdog": sum(1 for x in results if x["win_prob"] < 50),
            "ignored_locked": len(ignored_win), "ignored_lost": len(ignored_loss) + len(base.get("skipped", [])),
            "finished": len(base.get("finished", [])),
            "swing_wins": round(sum(x["win_prob"] for x in results) / 100, 1),
        },
        "results": results,
        "note": f"Shows only matchups between {int(LOW)}% and {int(HIGH)}% win probability with players still to play. "
                "'Needs' scales each remaining player's projection to the total required — the share he has to deliver.",
    }
