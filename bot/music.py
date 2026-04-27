import asyncio
import json
import logging
import re
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass

import discord
import yt_dlp
from discord.ext import commands

log = logging.getLogger("bot.music")

YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": False,
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    },
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin",
    "options": "-vn",
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _http_get(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _resolve_spotify(url: str) -> str:
    try:
        oembed_url = "https://open.spotify.com/oembed?url=" + urllib.parse.quote(url, safe="")
        data = json.loads(_http_get(oembed_url))
        title = data.get("title", "").strip()
        if title:
            return title
    except Exception:
        log.warning("Spotify oembed failed, falling back to HTML scrape", exc_info=True)
    try:
        html = _http_get(url)
        m_title = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        m_desc = re.search(r'<meta property="og:description" content="([^"]+)"', html)
        title = (m_title.group(1) if m_title else "").strip()
        desc = (m_desc.group(1) if m_desc else "").strip()
        artist = ""
        m_artist = re.search(r"Song[^·•]+[·•]\s*([^·•]+?)(?:\s*[·•]|$)", desc)
        if m_artist:
            artist = m_artist.group(1).strip()
        elif " · " in desc:
            artist = desc.split(" · ", 1)[0].strip()
        return f"{title} {artist}".strip() or url
    except Exception:
        log.exception("Spotify scrape failed")
        return url


def _resolve_apple_music(url: str) -> str:
    try:
        html = _http_get(url)
        m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        title = m.group(1).strip() if m else ""
        title = re.sub(r"\s*[-–]\s*Apple Music$", "", title)
        title = re.sub(r"\s*on Apple Music$", "", title)
        m2 = re.search(r'<meta name="apple:title" content="([^"]+)"', html)
        if not title and m2:
            title = m2.group(1).strip()
        m3 = re.search(r'<meta name="description" content="([^"]+)"', html)
        artist = ""
        if m3:
            d = m3.group(1)
            ma = re.search(r"by\s+(.+?)(?:\.|$|\s+on\s+Apple)", d)
            if ma:
                artist = ma.group(1).strip()
        return f"{title} {artist}".strip() or url
    except Exception:
        log.exception("Apple Music scrape failed")
        return url


def resolve_query(query: str) -> str:
    """Turn any URL or string into something yt-dlp can search/play."""
    q = query.strip()
    if "spotify.com" in q or q.startswith("spotify:"):
        if q.startswith("spotify:track:"):
            track_id = q.split(":")[-1]
            q = f"https://open.spotify.com/track/{track_id}"
        return _resolve_spotify(q)
    if "music.apple.com" in q:
        return _resolve_apple_music(q)
    return q  # YouTube, SoundCloud, Bandcamp etc. handled by yt-dlp directly


@dataclass
class Track:
    title: str
    stream_url: str
    duration: int | None
    requester: discord.abc.User
    webpage_url: str

    def fmt_duration(self) -> str:
        if not self.duration:
            return "live/?"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"


class MusicControlsView(discord.ui.View):
    def __init__(self, player: "GuildPlayer"):
        super().__init__(timeout=None)
        self.player = player
        self._sync_buttons()

    def _sync_buttons(self):
        vc = self.player.voice
        is_paused = bool(vc and vc.is_paused())
        self.pause_resume.label = "Resume" if is_paused else "Pause"
        self.pause_resume.emoji = "▶️" if is_paused else "⏸️"
        self.loop_btn.style = (
            discord.ButtonStyle.success if self.player.loop else discord.ButtonStyle.secondary
        )

    async def _check_voice(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "Kamu harus join voice channel dulu.", ephemeral=True
            )
            return False
        vc = self.player.voice
        if vc and interaction.user.voice.channel.id != vc.channel.id:
            await interaction.response.send_message(
                "Kamu harus di voice channel yang sama dengan bot.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Pause", emoji="⏸️", style=discord.ButtonStyle.primary)
    async def pause_resume(self, interaction: discord.Interaction, _b):
        if not await self._check_voice(interaction):
            return
        vc = self.player.voice
        if not vc or (not vc.is_playing() and not vc.is_paused()):
            await interaction.response.send_message("Lagi nggak ada yang diputar.", ephemeral=True)
            return
        if vc.is_paused():
            vc.resume()
        else:
            vc.pause()
        self._sync_buttons()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, _b):
        if not await self._check_voice(interaction):
            return
        vc = self.player.voice
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ Skip.", ephemeral=True)
        else:
            await interaction.response.send_message("Lagi nggak ada yang diputar.", ephemeral=True)

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.secondary)
    async def loop_btn(self, interaction: discord.Interaction, _b):
        if not await self._check_voice(interaction):
            return
        self.player.loop = not self.player.loop
        self._sync_buttons()
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            f"🔁 Loop: **{'ON' if self.player.loop else 'OFF'}**", ephemeral=True
        )

    @discord.ui.button(label="Queue", emoji="📜", style=discord.ButtonStyle.secondary)
    async def queue_btn(self, interaction: discord.Interaction, _b):
        p = self.player
        if not p.current and not p.queue:
            await interaction.response.send_message("Antrian kosong.", ephemeral=True)
            return
        embed = discord.Embed(title="Antrian", color=discord.Color.blurple())
        if p.current:
            embed.add_field(
                name="Now Playing",
                value=f"[{p.current.title}]({p.current.webpage_url}) — `{p.current.fmt_duration()}`",
                inline=False,
            )
        if p.queue:
            lines = []
            for i, t in enumerate(list(p.queue)[:10], start=1):
                lines.append(f"`{i}.` [{t.title}]({t.webpage_url}) — `{t.fmt_duration()}`")
            embed.add_field(
                name=f"Selanjutnya ({len(p.queue)})", value="\n".join(lines), inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop_btn(self, interaction: discord.Interaction, _b):
        if not await self._check_voice(interaction):
            return
        self.player.queue.clear()
        self.player.loop = False
        vc = self.player.voice
        if vc:
            vc.stop()
            await vc.disconnect()
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("⏹️ Diberhentiin & keluar dari voice.", ephemeral=True)


class GuildPlayer:
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.queue: deque[Track] = deque()
        self.current: Track | None = None
        self.volume: float = 0.5
        self.loop: bool = False
        self._next = asyncio.Event()
        self._task = bot.loop.create_task(self._player_loop())
        self.text_channel: discord.abc.MessageableChannel | None = None
        self._np_message: discord.Message | None = None

    @property
    def voice(self) -> discord.VoiceClient | None:
        vc = self.guild.voice_client
        return vc if isinstance(vc, discord.VoiceClient) else None

    async def _player_loop(self):
        while True:
            self._next.clear()
            if self.loop and self.current:
                track = self.current
            else:
                try:
                    track = await asyncio.wait_for(self._get_next(), timeout=300)
                except asyncio.TimeoutError:
                    if self.voice:
                        await self.voice.disconnect()
                    return await self._destroy()
            self.current = track
            vc = self.voice
            if not vc:
                return await self._destroy()
            try:
                source = discord.FFmpegPCMAudio(track.stream_url, **FFMPEG_OPTS)
                source = discord.PCMVolumeTransformer(source, volume=self.volume)
                vc.play(source, after=lambda _err: self.bot.loop.call_soon_threadsafe(self._next.set))
                if self.text_channel and not self.loop:
                    embed = discord.Embed(
                        title="Now Playing",
                        description=f"[{track.title}]({track.webpage_url})",
                        color=discord.Color.green(),
                    )
                    embed.add_field(name="Durasi", value=track.fmt_duration())
                    embed.add_field(name="Diminta oleh", value=track.requester.mention)
                    try:
                        if self._np_message:
                            try:
                                await self._np_message.edit(view=None)
                            except discord.HTTPException:
                                pass
                        view = MusicControlsView(self)
                        self._np_message = await self.text_channel.send(embed=embed, view=view)
                    except discord.HTTPException:
                        pass
                await self._next.wait()
            except Exception:
                log.exception("Player loop error")
                if self.text_channel:
                    try:
                        await self.text_channel.send(f"Error pas mainin **{track.title}**, skip.")
                    except discord.HTTPException:
                        pass

    async def _get_next(self) -> Track:
        while not self.queue:
            await asyncio.sleep(1)
        return self.queue.popleft()

    async def _destroy(self):
        cog = self.bot.get_cog("Music")
        if cog and hasattr(cog, "players"):
            cog.players.pop(self.guild.id, None)  # type: ignore[attr-defined]
        if not self._task.done():
            self._task.cancel()


def _extract(query: str) -> dict:
    info = ytdl.extract_info(query, download=False)
    if "entries" in info:
        if not info["entries"]:
            raise RuntimeError("No results found")
        info = info["entries"][0]
    return info


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: dict[int, GuildPlayer] = {}

    def get_player(self, guild: discord.Guild) -> GuildPlayer:
        player = self.players.get(guild.id)
        if not player:
            player = GuildPlayer(self.bot, guild)
            self.players[guild.id] = player
        return player

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Argumen kurang: `{error.param.name}`. Cek `m/help`.")
            return
        log.exception("Music command error", exc_info=error)
        try:
            await ctx.send(f"Error: `{error}`")
        except discord.HTTPException:
            pass

    async def ensure_voice(self, ctx: commands.Context) -> discord.VoiceClient | None:
        if not ctx.guild:
            await ctx.send("Command ini cuma bisa dipakai di server.")
            return None
        if not isinstance(ctx.author, discord.Member) or not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("Kamu harus join voice channel dulu.")
            return None
        channel = ctx.author.voice.channel
        perms = channel.permissions_for(ctx.guild.me)
        if not perms.connect or not perms.speak:
            await ctx.send("Aku nggak punya izin untuk join atau ngomong di voice channel kamu.")
            return None
        vc = ctx.guild.voice_client
        if isinstance(vc, discord.VoiceClient):
            if vc.channel.id != channel.id:
                await vc.move_to(channel)
            return vc
        try:
            return await channel.connect(timeout=15.0, reconnect=True)
        except Exception as e:
            log.exception("Failed to connect to voice")
            await ctx.send(f"Gagal join voice: `{e}`")
            return None

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        vc = await self.ensure_voice(ctx)
        if not vc or not ctx.guild:
            return
        async with ctx.typing():
            search = await asyncio.to_thread(resolve_query, query)
            try:
                info = await asyncio.to_thread(_extract, search)
            except Exception as e:
                log.exception("yt-dlp failed")
                await ctx.send(f"Gagal ambil lagu untuk `{query}`: `{e}`")
                return
        track = Track(
            title=info.get("title", "Unknown"),
            stream_url=info["url"],
            duration=info.get("duration"),
            requester=ctx.author,
            webpage_url=info.get("webpage_url", search),
        )
        player = self.get_player(ctx.guild)
        player.text_channel = ctx.channel
        player.queue.append(track)
        embed = discord.Embed(
            title="Ditambahkan ke antrian",
            description=f"[{track.title}]({track.webpage_url})",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Durasi", value=track.fmt_duration())
        embed.add_field(name="Posisi", value=str(len(player.queue)))
        await ctx.send(embed=embed)

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context):
        vc = ctx.guild and ctx.guild.voice_client
        if not isinstance(vc, discord.VoiceClient) or not vc.is_playing():
            await ctx.send("Lagi nggak ada yang diputar.")
            return
        vc.stop()
        await ctx.send("⏭️ Skip.")

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        if not ctx.guild:
            return
        player = self.players.get(ctx.guild.id)
        if player:
            player.queue.clear()
            player.loop = False
        vc = ctx.guild.voice_client
        if isinstance(vc, discord.VoiceClient):
            vc.stop()
        await ctx.send("⏹️ Diberhentiin & antrian dikosongin.")

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        vc = ctx.guild and ctx.guild.voice_client
        if isinstance(vc, discord.VoiceClient) and vc.is_playing():
            vc.pause()
            await ctx.send("⏸️ Dipause.")
        else:
            await ctx.send("Lagi nggak ada yang diputar.")

    @commands.command(name="resume")
    async def resume(self, ctx: commands.Context):
        vc = ctx.guild and ctx.guild.voice_client
        if isinstance(vc, discord.VoiceClient) and vc.is_paused():
            vc.resume()
            await ctx.send("▶️ Lanjut.")
        else:
            await ctx.send("Lagi nggak dipause.")

    @commands.command(name="leave", aliases=["disconnect", "dc", "stopplay"])
    async def leave(self, ctx: commands.Context):
        if not ctx.guild:
            return
        vc = ctx.guild.voice_client
        if isinstance(vc, discord.VoiceClient):
            await vc.disconnect()
            player = self.players.pop(ctx.guild.id, None)
            if player and not player._task.done():
                player._task.cancel()
            await ctx.send("👋 Keluar dari voice.")
        else:
            await ctx.send("Aku nggak lagi di voice channel.")

    @commands.command(name="queue", aliases=["q"])
    async def queue_cmd(self, ctx: commands.Context):
        if not ctx.guild:
            return
        player = self.players.get(ctx.guild.id)
        if not player or (not player.current and not player.queue):
            await ctx.send("Antrian kosong.")
            return
        embed = discord.Embed(title="Antrian", color=discord.Color.blurple())
        if player.current:
            embed.add_field(
                name="Now Playing",
                value=f"[{player.current.title}]({player.current.webpage_url}) — `{player.current.fmt_duration()}`",
                inline=False,
            )
        if player.queue:
            lines = []
            for i, t in enumerate(list(player.queue)[:10], start=1):
                lines.append(f"`{i}.` [{t.title}]({t.webpage_url}) — `{t.fmt_duration()}`")
            embed.add_field(name=f"Selanjutnya ({len(player.queue)})", value="\n".join(lines), inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx: commands.Context):
        if not ctx.guild:
            return
        player = self.players.get(ctx.guild.id)
        if not player or not player.current:
            await ctx.send("Lagi nggak ada yang diputar.")
            return
        t = player.current
        embed = discord.Embed(
            title="Now Playing",
            description=f"[{t.title}]({t.webpage_url})",
            color=discord.Color.green(),
        )
        embed.add_field(name="Durasi", value=t.fmt_duration())
        embed.add_field(name="Diminta oleh", value=t.requester.mention)
        await ctx.send(embed=embed)

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, level: int):
        if not ctx.guild:
            return
        if not (0 <= level <= 200):
            await ctx.send("Volume harus 0–200.")
            return
        player = self.players.get(ctx.guild.id)
        if not player:
            await ctx.send("Lagi nggak ada yang diputar.")
            return
        player.volume = level / 100
        vc = ctx.guild.voice_client
        if isinstance(vc, discord.VoiceClient) and vc.source and isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = player.volume
        await ctx.send(f"🔊 Volume: **{level}%**")

    @commands.command(name="loop")
    async def loop(self, ctx: commands.Context):
        if not ctx.guild:
            return
        player = self.players.get(ctx.guild.id)
        if not player:
            await ctx.send("Lagi nggak ada yang diputar.")
            return
        player.loop = not player.loop
        await ctx.send(f"🔁 Loop: **{'ON' if player.loop else 'OFF'}**")

    @commands.command(name="clear")
    async def clear_queue(self, ctx: commands.Context):
        if not ctx.guild:
            return
        player = self.players.get(ctx.guild.id)
        if not player or not player.queue:
            await ctx.send("Antrian udah kosong.")
            return
        n = len(player.queue)
        player.queue.clear()
        await ctx.send(f"🗑️ Hapus {n} lagu dari antrian.")

    @commands.command(name="help", aliases=["h", "commands"])
    async def music_help(self, ctx: commands.Context):
        p = "m/"
        embed = discord.Embed(
            title="Music Commands",
            description=f"Prefix: `{p}` · Sumber: YouTube, SoundCloud, Bandcamp, Spotify URL, Apple Music URL, atau pencarian bebas",
            color=discord.Color.purple(),
        )
        embed.add_field(name=f"{p}play <query/URL>", value="Putar lagu / tambah ke antrian (alias: `p`).", inline=False)
        embed.add_field(name=f"{p}skip", value="Skip lagu sekarang (alias: `s`).", inline=False)
        embed.add_field(name=f"{p}stop", value="Stop & kosongin antrian.", inline=False)
        embed.add_field(name=f"{p}pause / {p}resume", value="Pause / lanjutin pemutaran.", inline=False)
        embed.add_field(name=f"{p}queue", value="Lihat antrian (alias: `q`).", inline=False)
        embed.add_field(name=f"{p}nowplaying", value="Lihat lagu sekarang (alias: `np`).", inline=False)
        embed.add_field(name=f"{p}volume <0-200>", value="Atur volume (alias: `vol`).", inline=False)
        embed.add_field(name=f"{p}loop", value="Toggle loop lagu sekarang.", inline=False)
        embed.add_field(name=f"{p}clear", value="Hapus semua lagu di antrian.", inline=False)
        embed.add_field(name=f"{p}leave", value="Keluar dari voice channel (alias: `dc`).", inline=False)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
    log.info("Music cog loaded.")
