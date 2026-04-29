import asyncio
import json
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "stats.json"
DATA_FILE.parent.mkdir(exist_ok=True)
_lock = asyncio.Lock()


def _load() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    tmp = DATA_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(DATA_FILE)


DEFAULT_USER = {
    "points": 0,
    "wins": 0,
    "losses": 0,
    "played": 0,
    "games": {},
    "xp": 0,
    "level": 0,
    "messages": 0,
    "voice_seconds": 0,
    "last_xp_ts": 0.0,
    "last_daily": "",
    "daily_streak": 0,
}


def _get_user(data: dict, guild_id: int, user_id: int) -> dict:
    g = data.setdefault(str(guild_id), {})
    u = g.setdefault(str(user_id), {})
    for k, v in DEFAULT_USER.items():
        u.setdefault(k, v.copy() if isinstance(v, dict) else v)
    return u


def level_from_xp(xp: int) -> int:
    """xp_for_level(n) = 50 * n * (n+1). Inverse: n = floor((sqrt(1+0.16*xp)-1)/2)."""
    if xp <= 0:
        return 0
    import math
    return int((math.sqrt(1 + 0.16 * xp) - 1) / 2)


def xp_for_level(n: int) -> int:
    return 50 * n * (n + 1)


def xp_to_next(xp: int) -> tuple[int, int, int]:
    """Returns (current_level, xp_into_level, xp_needed_for_next_level)."""
    cur = level_from_xp(xp)
    base = xp_for_level(cur)
    nxt = xp_for_level(cur + 1)
    return cur, xp - base, nxt - base


async def add_xp(guild_id: int, user_id: int, amount: int) -> tuple[dict, int | None]:
    """Returns (user_dict, new_level if leveled up else None)."""
    async with _lock:
        data = _load()
        u = _get_user(data, guild_id, user_id)
        old_level = level_from_xp(u.get("xp", 0))
        u["xp"] = u.get("xp", 0) + amount
        new_level = level_from_xp(u["xp"])
        u["level"] = new_level
        _save(data)
        leveled = new_level if new_level > old_level else None
        return dict(u), leveled


async def add_message(guild_id: int, user_id: int) -> None:
    async with _lock:
        data = _load()
        u = _get_user(data, guild_id, user_id)
        u["messages"] = u.get("messages", 0) + 1
        _save(data)


async def add_voice_seconds(guild_id: int, user_id: int, seconds: int) -> None:
    async with _lock:
        data = _load()
        u = _get_user(data, guild_id, user_id)
        u["voice_seconds"] = u.get("voice_seconds", 0) + seconds
        _save(data)


async def get_xp_cooldown(guild_id: int, user_id: int) -> float:
    async with _lock:
        data = _load()
        u = _get_user(data, guild_id, user_id)
        return float(u.get("last_xp_ts", 0.0))


async def set_xp_cooldown(guild_id: int, user_id: int, ts: float) -> None:
    async with _lock:
        data = _load()
        u = _get_user(data, guild_id, user_id)
        u["last_xp_ts"] = ts
        _save(data)


async def claim_daily(guild_id: int, user_id: int, today: str, reward: int) -> tuple[bool, int, int]:
    """Returns (claimed, new_streak, total_reward). claimed=False if already claimed today."""
    async with _lock:
        data = _load()
        u = _get_user(data, guild_id, user_id)
        if u.get("last_daily") == today:
            return False, u.get("daily_streak", 0), 0
        # streak: if last_daily was yesterday (we don't compute yesterday strictly; just bump)
        from datetime import date, timedelta
        try:
            last = date.fromisoformat(u.get("last_daily") or "1970-01-01")
            today_d = date.fromisoformat(today)
            if (today_d - last).days == 1:
                u["daily_streak"] = u.get("daily_streak", 0) + 1
            else:
                u["daily_streak"] = 1
        except ValueError:
            u["daily_streak"] = 1
        bonus = min(u["daily_streak"] - 1, 7) * 25
        total = reward + bonus
        u["points"] = u.get("points", 0) + total
        u["last_daily"] = today
        _save(data)
        return True, u["daily_streak"], total


async def add_points(guild_id: int, user_id: int, points: int, game: str) -> dict:
    async with _lock:
        data = _load()
        u = _get_user(data, guild_id, user_id)
        u["points"] = u.get("points", 0) + points
        u["wins"] = u.get("wins", 0) + (1 if points > 0 else 0)
        u["played"] = u.get("played", 0) + 1
        games = u.setdefault("games", {})
        games[game] = games.get(game, 0) + 1
        _save(data)
        return dict(u)


async def add_loss(guild_id: int, user_id: int, game: str) -> dict:
    async with _lock:
        data = _load()
        u = _get_user(data, guild_id, user_id)
        u["losses"] = u.get("losses", 0) + 1
        u["played"] = u.get("played", 0) + 1
        games = u.setdefault("games", {})
        games[game] = games.get(game, 0) + 1
        _save(data)
        return dict(u)


async def get_stats(guild_id: int, user_id: int) -> dict:
    async with _lock:
        data = _load()
        return dict(_get_user(data, guild_id, user_id))


async def top(guild_id: int, n: int = 10) -> list[tuple[str, int]]:
    async with _lock:
        data = _load()
        users = data.get(str(guild_id), {})
        ranked = sorted(
            ((uid, u.get("points", 0)) for uid, u in users.items()),
            key=lambda x: -x[1],
        )
        return ranked[:n]


async def rank_of(guild_id: int, user_id: int) -> tuple[int, int]:
    async with _lock:
        data = _load()
        users = data.get(str(guild_id), {})
        ranked = sorted(
            users.items(), key=lambda kv: -kv[1].get("points", 0)
        )
        for idx, (uid, _) in enumerate(ranked, start=1):
            if uid == str(user_id):
                return idx, len(ranked)
        return 0, len(ranked)
