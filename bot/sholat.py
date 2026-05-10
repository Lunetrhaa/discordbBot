"""Pengingat sholat 5 waktu (WIB / Jakarta). Pakai jadwal statis approx;
bisa diatur per-guild di /setsholat."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from . import config as cfg

log = logging.getLogger("bot.sholat")

JAKARTA = timezone(timedelta(hours=7))

# Jadwal approx Jakarta (HH, MM)
PRAYERS = [
    ("Subuh",   4, 35, "🌅"),
    ("Dzuhur", 12,  0, "☀️"),
    ("Ashar",  15, 15, "🌤️"),
    ("Maghrib", 17, 55, "🌇"),
    ("Isya",   19, 10, "🌙"),
]

NIAT = {
    "Subuh":   "Ushalli fardhash-shubhi rak'ataini mustaqbilal qiblati ada'an lillahi ta'ala.",
    "Dzuhur":  "Ushalli fardhazh-zhuhri arba'a raka'aatin mustaqbilal qiblati ada'an lillahi ta'ala.",
    "Ashar":   "Ushalli fardhal 'ashri arba'a raka'aatin mustaqbilal qiblati ada'an lillahi ta'ala.",
    "Maghrib": "Ushalli fardhal maghribi tsalaatsa raka'aatin mustaqbilal qiblati ada'an lillahi ta'ala.",
    "Isya":    "Ushalli fardhal 'isya'i arba'a raka'aatin mustaqbilal qiblati ada'an lillahi ta'ala.",
}


class SholatCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._fired_today: set[tuple[int, str, str]] = set()  # (guild_id, name, date_str)
        self.minute_tick.start()

    def cog_unload(self):
        self.minute_tick.cancel()

    @tasks.loop(seconds=30)
    async def minute_tick(self):
        now = datetime.now(JAKARTA)
        today_str = now.strftime("%Y-%m-%d")
        # Drop yesterday's keys to keep set small
        self._fired_today = {k for k in self._fired_today if k[2] == today_str}
        for guild in list(self.bot.guilds):
            guild_cfg = await cfg.get_guild(guild.id)
            if not guild_cfg.get("sholat_enabled"):
                continue
            chan_id = guild_cfg.get("sholat_channel")
            if not chan_id:
                # Fallback: cari channel yang namanya mengandung 'truth' atau 'tod'
                target = None
                for ch in guild.text_channels:
                    nm = ch.name.lower()
                    if "truth-or-dare" in nm or "truth_or_dare" in nm or "tod" == nm:
                        target = ch
                        break
                if not target:
                    continue
            else:
                target = self.bot.get_channel(int(chan_id))
            if not isinstance(target, (discord.TextChannel, discord.Thread)):
                continue
            for name, hh, mm, emoji in PRAYERS:
                key = (guild.id, name, today_str)
                if key in self._fired_today:
                    continue
                if now.hour == hh and now.minute == mm:
                    self._fired_today.add(key)
                    try:
                        embed = discord.Embed(
                            title=f"{emoji} Waktu Sholat {name}",
                            description=f"Sudah masuk waktu sholat **{name}** (WIB {hh:02d}:{mm:02d}).\n"
                                        "Yuk ambil wudhu dan tunaikan sholat dulu. 🤲",
                            color=discord.Color.from_str("#1abc9c"),
                        )
                        embed.add_field(name="Niat", value=NIAT.get(name, "—"), inline=False)
                        embed.set_footer(text="Lunethra • Pengingat sholat WIB")
                        await target.send(embed=embed)
                    except (discord.Forbidden, discord.HTTPException):
                        pass

    @minute_tick.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="setsholat", description="[ADMIN] Aktifkan/atur channel pengingat sholat.")
    @app_commands.describe(
        channel="Channel tujuan (default: cari channel truth-or-dare)",
        enable="True buat aktifkan, False buat matikan",
    )
    @app_commands.default_permissions(administrator=True)
    async def setsholat(
        self,
        interaction: discord.Interaction,
        enable: bool = True,
        channel: discord.TextChannel | None = None,
    ):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admin only.", ephemeral=True)
            return
        await cfg.set_guild_field(interaction.guild.id, "sholat_enabled", enable)
        if channel:
            await cfg.set_guild_field(interaction.guild.id, "sholat_channel", str(channel.id))
        msg = (
            f"✅ Pengingat sholat **{'aktif' if enable else 'nonaktif'}**"
            + (f" di {channel.mention}" if channel else " (auto-detect channel #truth-or-dare)")
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="jadwalsholat", description="Lihat jadwal sholat hari ini (WIB).")
    async def jadwal(self, interaction: discord.Interaction):
        now = datetime.now(JAKARTA)
        embed = discord.Embed(
            title=f"🕌 Jadwal Sholat — {now.strftime('%d %b %Y')} WIB",
            color=discord.Color.from_str("#1abc9c"),
        )
        for name, hh, mm, emoji in PRAYERS:
            embed.add_field(name=f"{emoji} {name}", value=f"**{hh:02d}:{mm:02d}**", inline=True)
        embed.set_footer(text="Jadwal approx Jakarta. Sesuaikan dengan jadwal masjid setempat ya.")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SholatCog(bot))
    log.info("Sholat cog loaded.")
