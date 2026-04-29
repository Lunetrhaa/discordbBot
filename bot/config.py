"""Per-guild config storage shared with the admin web panel."""
import asyncio
import json
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "data" / "config.json"
CONFIG_FILE.parent.mkdir(exist_ok=True)
_lock = asyncio.Lock()

DEFAULT_GUILD = {
    "welcome_channel": None,
    "welcome_image": None,
    "welcome_text": "Selamat datang di **{server}**, {user}! Kamu member ke-**{count}**.",
    "welcome_color": "#5865F2",
    "goodbye_channel": None,
    "goodbye_image": None,
    "goodbye_text": "Sampai jumpa, **{user}**. 😢",
    "goodbye_color": "#ED4245",
    "level_up_channel": None,
    "level_up_enabled": True,
    "sholat_channel": None,
    "sholat_enabled": False,
    "voicemaster_create_channel": None,
    "voicemaster_category": None,
    "confess_channel": None,
    "verify_channel": None,
    "verify_message_id": None,
    "verify_emoji": "✅",
    "verify_role": None,
}


def _load() -> dict:
    if not CONFIG_FILE.exists():
        return {"guilds": {}}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"guilds": {}}


def _save(data: dict) -> None:
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CONFIG_FILE)


def _get(data: dict, guild_id: int) -> dict:
    guilds = data.setdefault("guilds", {})
    g = guilds.setdefault(str(guild_id), {})
    for k, v in DEFAULT_GUILD.items():
        g.setdefault(k, v)
    return g


async def get_guild(guild_id: int) -> dict:
    async with _lock:
        data = _load()
        return dict(_get(data, guild_id))


async def set_guild_field(guild_id: int, field: str, value) -> dict:
    if field not in DEFAULT_GUILD:
        raise KeyError(f"Unknown config field: {field}")
    async with _lock:
        data = _load()
        g = _get(data, guild_id)
        g[field] = value
        _save(data)
        return dict(g)


async def update_guild(guild_id: int, updates: dict) -> dict:
    async with _lock:
        data = _load()
        g = _get(data, guild_id)
        for k, v in updates.items():
            if k in DEFAULT_GUILD:
                g[k] = v
        _save(data)
        return dict(g)
