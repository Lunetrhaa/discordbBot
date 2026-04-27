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


def _get_user(data: dict, guild_id: int, user_id: int) -> dict:
    g = data.setdefault(str(guild_id), {})
    return g.setdefault(
        str(user_id),
        {"points": 0, "wins": 0, "losses": 0, "played": 0, "games": {}},
    )


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
