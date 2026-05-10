"""React-to-verify: user reacts ✅ on the verify message → bot grants role."""
import logging

import discord
from discord import app_commands
from discord.ext import commands

from . import config as cfg

log = logging.getLogger("bot.verify")


class VerifyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return
        guild_cfg = await cfg.get_guild(payload.guild_id)
        msg_id = guild_cfg.get("verify_message_id")
        role_id = guild_cfg.get("verify_role")
        emoji_cfg = guild_cfg.get("verify_emoji") or "✅"
        if not msg_id or not role_id:
            return
        if str(payload.message_id) != str(msg_id):
            return
        if str(payload.emoji) != emoji_cfg and payload.emoji.name != emoji_cfg:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(int(role_id))
        if not role:
            return
        member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
        if not member or member.bot or role in member.roles:
            return
        try:
            await member.add_roles(role, reason="Verified via reaction")
        except discord.Forbidden:
            log.warning("verify: missing permission to add role in %s", guild.id)
        except discord.HTTPException as e:
            log.warning("verify: add_roles failed: %s", e)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return
        guild_cfg = await cfg.get_guild(payload.guild_id)
        msg_id = guild_cfg.get("verify_message_id")
        role_id = guild_cfg.get("verify_role")
        emoji_cfg = guild_cfg.get("verify_emoji") or "✅"
        if not msg_id or not role_id:
            return
        if str(payload.message_id) != str(msg_id):
            return
        if str(payload.emoji) != emoji_cfg and payload.emoji.name != emoji_cfg:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(int(role_id))
        if not role:
            return
        member = guild.get_member(payload.user_id)
        if not member or member.bot or role not in member.roles:
            return
        try:
            await member.remove_roles(role, reason="Unverified via reaction")
        except (discord.Forbidden, discord.HTTPException):
            pass

    @app_commands.command(
        name="setverify",
        description="[ADMIN] Setup react-to-verify (kayak Carl bot).",
    )
    @app_commands.describe(
        channel="Channel verify (mis. #verify)",
        role="Role yang dikasih kalau user react",
        emoji="Emoji buat react (default ✅)",
        title="Judul embed (opsional)",
        description="Isi embed (opsional)",
    )
    @app_commands.default_permissions(administrator=True)
    async def setverify(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        role: discord.Role,
        emoji: str = "✅",
        title: str | None = None,
        description: str | None = None,
    ):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admin only.", ephemeral=True)
            return
        # Cek bot bisa kasih role ini
        me = interaction.guild.me
        if me.top_role <= role:
            await interaction.response.send_message(
                f"❌ Role bot harus di **atas** role `{role.name}` di hierarchy. Geser role bot lebih tinggi dulu.",
                ephemeral=True,
            )
            return
        if not channel.permissions_for(me).send_messages or not channel.permissions_for(me).add_reactions:
            await interaction.response.send_message(
                f"❌ Bot butuh permission **Send Messages** & **Add Reactions** di {channel.mention}.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title=title or "🔒 Verifikasi",
            description=(description or
                f"Klik reaksi {emoji} di bawah pesan ini buat dapetin role **{role.name}** "
                "& akses penuh ke server.\n\n"
                "Dengan verify kamu setuju dengan rules server. ✨"),
            color=discord.Color.from_str("#57f287"),
        )
        embed.set_footer(text="Lunethra • React to verify")
        try:
            msg = await channel.send(embed=embed)
            await msg.add_reaction(emoji)
        except discord.HTTPException as e:
            await interaction.followup.send(f"Gagal kirim pesan verify: `{e}`")
            return
        await cfg.update_guild(interaction.guild.id, {
            "verify_channel": str(channel.id),
            "verify_message_id": str(msg.id),
            "verify_emoji": emoji,
            "verify_role": str(role.id),
        })
        await interaction.followup.send(
            f"✅ Verify aktif di {channel.mention}. User yang react {emoji} dapet role {role.mention}.\n"
            f"Message ID: `{msg.id}`",
        )

    @app_commands.command(name="unsetverify", description="[ADMIN] Matikan react-to-verify.")
    @app_commands.default_permissions(administrator=True)
    async def unsetverify(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admin only.", ephemeral=True)
            return
        await cfg.update_guild(interaction.guild.id, {
            "verify_message_id": None,
            "verify_role": None,
        })
        await interaction.response.send_message("✅ Verify dimatikan.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(VerifyCog(bot))
    log.info("Verify cog loaded.")
