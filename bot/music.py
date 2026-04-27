import asyncio
import logging
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
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin",
    "options": "-vn",
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)


@dataclass
class Track:
    title: str
    url: str
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
                        await self.text_channel.send(embed=embed)
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
        cog: "Music" | None = self.bot.get_cog("Music")  # type: ignore[assignment]
        if cog:
            cog.players.pop(self.guild.id, None)
        if not self._task.done():
            self._task.cancel()


def _extract(query: str) -> dict:
    info = ytdl.extract_info(query, download=False)
    if "entries" in info:
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

    async def ensure_voice(self, ctx: commands.Context) -> discord.VoiceClient | None:
        if not ctx.guild:
            await ctx.send("Command ini cuma bisa dipakai di server.")
            return None
        if not isinstance(ctx.author, discord.Member) or not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("Kamu harus join voice channel dulu.")
            return None
        channel = ctx.author.voice.channel
        vc = ctx.guild.voice_client
        if isinstance(vc, discord.VoiceClient):
            if vc.channel.id != channel.id:
                await vc.move_to(channel)
            return vc
        return await channel.connect()

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        vc = await self.ensure_voice(ctx)
        if not vc or not ctx.guild:
            return
        async with ctx.typing():
            try:
                info = await asyncio.to_thread(_extract, query)
            except Exception as e:
                log.exception("yt-dlp failed")
                await ctx.send(f"Gagal ambil lagu: `{e}`")
                return
        track = Track(
            title=info.get("title", "Unknown"),
            url=info.get("url"),
            stream_url=info["url"],
            duration=info.get("duration"),
            requester=ctx.author,
            webpage_url=info.get("webpage_url", query),
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
            description=f"Prefix: `{p}`",
            color=discord.Color.purple(),
        )
        embed.add_field(name=f"{p}play <query>", value="Putar lagu / tambah ke antrian (alias: `p`).", inline=False)
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
