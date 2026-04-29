import asyncio
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config as cfg
import stats as stats_mod

log = logging.getLogger("bot.levels")

CHAT_XP_MIN = 15
CHAT_XP_MAX = 25
CHAT_COOLDOWN = 60  # seconds
VOICE_XP_PER_TICK = 10
VOICE_TICK = 60  # seconds


class LevelsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # member_id -> (guild_id, joined_unix)
        self._voice_join: dict[int, tuple[int, float]] = {}
        self.voice_ticker.start()

    def cog_unload(self):
        self.voice_ticker.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.content.startswith(("m/", "/", "!", "?")):
            return
        await stats_mod.add_message(message.guild.id, message.author.id)
        last = await stats_mod.get_xp_cooldown(message.guild.id, message.author.id)
        now = time.time()
        if now - last < CHAT_COOLDOWN:
            return
        await stats_mod.set_xp_cooldown(message.guild.id, message.author.id, now)
        import random
        amount = random.randint(CHAT_XP_MIN, CHAT_XP_MAX)
        _, leveled = await stats_mod.add_xp(message.guild.id, message.author.id, amount)
        if leveled:
            await self._announce_level_up(message.channel, message.author, leveled, message.guild.id)

    async def _announce_level_up(
        self, fallback_channel, member: discord.abc.User, level: int, guild_id: int
    ):
        guild_cfg = await cfg.get_guild(guild_id)
        if not guild_cfg.get("level_up_enabled", True):
            return
        chan_id = guild_cfg.get("level_up_channel")
        target = None
        if chan_id and self.bot.get_channel(int(chan_id)):
            target = self.bot.get_channel(int(chan_id))
        else:
            target = fallback_channel
        if target is None:
            return
        try:
            embed = discord.Embed(
                title="✨ LEVEL UP!",
                description=f"Selamat {member.mention}, kamu naik ke **Level {level}**! 🎉",
                color=discord.Color.gold(),
            )
            if hasattr(member, "display_avatar"):
                embed.set_thumbnail(url=member.display_avatar.url)
            await target.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    @tasks.loop(seconds=VOICE_TICK)
    async def voice_ticker(self):
        now = time.time()
        for guild in list(self.bot.guilds):
            for vc in guild.voice_channels:
                eligible = [m for m in vc.members if not m.bot and not m.voice.deaf and not m.voice.self_deaf]
                if len(eligible) < 2:
                    continue
                for m in eligible:
                    await stats_mod.add_voice_seconds(guild.id, m.id, VOICE_TICK)
                    _, leveled = await stats_mod.add_xp(guild.id, m.id, VOICE_XP_PER_TICK)
                    if leveled:
                        await self._announce_level_up(vc, m, leveled, guild.id)

    @voice_ticker.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="level", description="Lihat level & XP kamu (atau orang lain).")
    @app_commands.describe(user="User yang mau dilihat (kosongin = kamu)")
    async def level(self, interaction: discord.Interaction, user: discord.Member | None = None):
        if not interaction.guild:
            await interaction.response.send_message("Cuma di server.", ephemeral=True)
            return
        target = user or interaction.user
        s = await stats_mod.get_stats(interaction.guild.id, target.id)
        xp = s.get("xp", 0)
        cur, into, span = stats_mod.xp_to_next(xp)
        bar_len = 20
        filled = int(bar_len * into / span) if span else 0
        bar = "█" * filled + "░" * (bar_len - filled)
        rank, total = await stats_mod.rank_of(interaction.guild.id, target.id)
        voice_min = s.get("voice_seconds", 0) // 60
        embed = discord.Embed(
            title=f"📈 Level — {target.display_name}",
            color=discord.Color.purple(),
        )
        if hasattr(target, "display_avatar"):
            embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=f"**{cur}**", inline=True)
        embed.add_field(name="XP", value=f"**{xp:,}** total", inline=True)
        embed.add_field(name="Peringkat poin", value=f"#{rank} / {total}" if rank else "—", inline=True)
        embed.add_field(name="Progress", value=f"`{bar}`\n{into:,} / {span:,} XP", inline=False)
        embed.add_field(name="💬 Pesan", value=f"{s.get('messages', 0):,}", inline=True)
        embed.add_field(name="🎙️ Voice", value=f"{voice_min:,} menit", inline=True)
        embed.add_field(name="🏆 Poin", value=f"{s.get('points', 0):,}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rank", description="Top 10 level di server ini.")
    async def rank(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Cuma di server.", ephemeral=True)
            return
        async with stats_mod._lock:
            data = stats_mod._load()
            users = data.get(str(interaction.guild.id), {})
        ranked = sorted(
            users.items(), key=lambda kv: -kv[1].get("xp", 0)
        )[:10]
        if not ranked:
            await interaction.response.send_message("Belum ada XP di sini.")
            return
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, u) in enumerate(ranked):
            try:
                member = interaction.guild.get_member(int(uid)) or await self.bot.fetch_user(int(uid))
                name = member.display_name if isinstance(member, discord.Member) else member.name
            except (discord.NotFound, ValueError):
                name = f"User#{uid}"
            lvl = stats_mod.level_from_xp(u.get("xp", 0))
            prefix = medals[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{prefix} **{name}** — Lv {lvl} ({u.get('xp', 0):,} XP)")
        embed = discord.Embed(
            title=f"📊 Rank — {interaction.guild.name}",
            description="\n".join(lines),
            color=discord.Color.purple(),
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelsCog(bot))
    log.info("Levels cog loaded.")
