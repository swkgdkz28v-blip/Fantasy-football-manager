from cachetools import TTLCache
import threading

# Thread-safe caches with TTL
_lock = threading.Lock()

# NFL state — cache 10 minutes
nfl_state_cache = TTLCache(maxsize=1, ttl=600)

# Players DB — cache 24 hours (rarely changes)
players_cache = TTLCache(maxsize=1, ttl=86400)

# User leagues — cache 5 minutes
leagues_cache = TTLCache(maxsize=100, ttl=300)

# Rosters — cache 3 minutes (changes during waiver/trade)
rosters_cache = TTLCache(maxsize=500, ttl=180)

# League users — cache 10 minutes
league_users_cache = TTLCache(maxsize=500, ttl=600)

# Projections — cache 30 minutes
projections_cache = TTLCache(maxsize=50, ttl=1800)

# Stats — cache 5 minutes (live games update)
stats_cache = TTLCache(maxsize=50, ttl=300)

# Matchups — cache 2 minutes
matchups_cache = TTLCache(maxsize=200, ttl=120)

# Trending adds/drops — 10 minutes
trending_cache = TTLCache(maxsize=10, ttl=600)

# NFL schedule with live game status — 2 minutes
schedule_cache = TTLCache(maxsize=4, ttl=120)

def get_cached(cache, key):
    with _lock:
        return cache.get(key)

def set_cached(cache, key, value):
    with _lock:
        cache[key] = value
    return value
