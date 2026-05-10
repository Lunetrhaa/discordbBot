import logging

import discord
from discord import app_commands
from discord.ext import commands

from . import config as cfg

log = logging.getLogger("bot.welcome")


def _format_text(template: str, member: discord.Member, count: int) -> str:
    return (
        template
        .replace("{user}", member.mention)
        .replace("{username}", member.display_name)
        .replace("{server}", member.guild.name)
        .replace("{count}", str(count))
    )


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        guild_cfg = await cfg.get_guild(member.guild.id)
        chan_id = guild_cfg.get("welcome_channel")
        if not chan_id:
            return
        chan = member.guild.get_channel(int(chan_id))
        if not isinstance(chan, (discord.TextChannel, discord.Thread)):
            return
        text = _format_text(guild_cfg.get("welcome_text", ""), member, member.guild.member_count or 0)
        try:
            color = discord.Color.from_str(guild_cfg.get("welcome_color") or "#5865F2")
        except ValueError:
            color = discord.Color.blurple()
        embed = discord.Embed(
            title="🎉 Welcome!",
            description=text,
            color=color,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        if guild_cfg.get("welcome_image"):
            embed.set_image(url=guild_cfg["welcome_image"])
        embed.set_footer(text=f"ID: {member.id}")
        try:
            await chan.send(content=member.mention, embed=embed)
        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning("welcome send failed: %s", e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            return
        guild_cfg = await cfg.get_guild(member.guild.id)
        chan_id = guild_cfg.get("goodbye_channel")
        if not chan_id:
            return
        chan = member.guild.get_channel(int(chan_id))
        if not isinstance(chan, (discord.TextChannel, discord.Thread)):
            return
        text = _format_text(guild_cfg.get("goodbye_text", ""), member, member.guild.member_count or 0)
        try:
            color = discord.Color.from_str(guild_cfg.get("goodbye_color") or "#ED4245")
        except ValueError:
            color = discord.Color.red()
        embed = discord.Embed(
            title="👋 Goodbye",
            description=text,
            color=color,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        if guild_cfg.get("goodbye_image"):
            embed.set_image(url=guild_cfg["goodbye_image"])
        try:
            await chan.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning("goodbye send failed: %s", e)

    @app_commands.command(name="setwelcome", description="[ADMIN] Set channel welcome member baru.")
    @app_commands.describe(channel="Channel tujuan")
    @app_commands.default_permissions(administrator=True)
    async def setwelcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admin only.", ephemeral=True)
            return
        await cfg.set_guild_field(interaction.guild.id, "welcome_channel", str(channel.id))
        await interaction.response.send_message(
            f"✅ Welcome channel di-set ke {channel.mention}. Edit teks/gambar lewat panel admin web.",
            ephemeral=True,
        )

    @app_commands.command(name="setgoodbye", description="[ADMIN] Set channel goodbye member keluar.")
    @app_commands.describe(channel="Channel tujuan")
    @app_commands.default_permissions(administrator=True)
    async def setgoodbye(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admin only.", ephemeral=True)
            return
        await cfg.set_guild_field(interaction.guild.id, "goodbye_channel", str(channel.id))
        await interaction.response.send_message(
            f"✅ Goodbye channel di-set ke {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="testwelcome", description="[ADMIN] Tes welcome message ke kamu sendiri.")
    @app_commands.default_permissions(administrator=True)
    async def testwelcome(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Cuma di server.", ephemeral=True)
            return
        await self.on_member_join(interaction.user)
        await interaction.response.send_message("✅ Sent test welcome.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
    log.info("Welcome cog loaded.")
