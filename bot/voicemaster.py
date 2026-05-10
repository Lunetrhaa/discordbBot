"""Voicemaster: when user joins the configured 'create' voice channel,
spin up a personal voice channel for them with control buttons."""
import logging

import discord
from discord import app_commands
from discord.ext import commands

from . import config as cfg

log = logging.getLogger("bot.voicemaster")

# guild_id -> {channel_id: owner_id}
_owned_channels: dict[int, dict[int, int]] = {}


class VoiceControlView(discord.ui.View):
    def __init__(self, owner_id: int, channel_id: int):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.channel_id = channel_id

    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "❌ Cuma owner channel ini yang bisa pakai tombol.", ephemeral=True
            )
            return False
        return True

    def _channel(self, interaction: discord.Interaction) -> discord.VoiceChannel | None:
        ch = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        if isinstance(ch, discord.VoiceChannel):
            return ch
        return None

    @discord.ui.button(label="Lock", emoji="🔒", style=discord.ButtonStyle.secondary, row=0)
    async def lock(self, interaction: discord.Interaction, _b):
        if not await self._check_owner(interaction):
            return
        ch = self._channel(interaction)
        if not ch:
            await interaction.response.send_message("Channel hilang.", ephemeral=True)
            return
        everyone = interaction.guild.default_role
        overwrites = ch.overwrites_for(everyone)
        overwrites.connect = False
        await ch.set_permissions(everyone, overwrite=overwrites)
        await interaction.response.send_message("🔒 Channel dikunci.", ephemeral=True)

    @discord.ui.button(label="Unlock", emoji="🔓", style=discord.ButtonStyle.secondary, row=0)
    async def unlock(self, interaction: discord.Interaction, _b):
        if not await self._check_owner(interaction):
            return
        ch = self._channel(interaction)
        if not ch:
            await interaction.response.send_message("Channel hilang.", ephemeral=True)
            return
        everyone = interaction.guild.default_role
        overwrites = ch.overwrites_for(everyone)
        overwrites.connect = None
        await ch.set_permissions(everyone, overwrite=overwrites)
        await interaction.response.send_message("🔓 Channel dibuka.", ephemeral=True)

    @discord.ui.button(label="Hide", emoji="👁️", style=discord.ButtonStyle.secondary, row=0)
    async def hide(self, interaction: discord.Interaction, _b):
        if not await self._check_owner(interaction):
            return
        ch = self._channel(interaction)
        if not ch:
            return
        everyone = interaction.guild.default_role
        overwrites = ch.overwrites_for(everyone)
        overwrites.view_channel = False
        await ch.set_permissions(everyone, overwrite=overwrites)
        await interaction.response.send_message("👁️ Channel disembunyikan.", ephemeral=True)

    @discord.ui.button(label="Show", emoji="👀", style=discord.ButtonStyle.secondary, row=0)
    async def show(self, interaction: discord.Interaction, _b):
        if not await self._check_owner(interaction):
            return
        ch = self._channel(interaction)
        if not ch:
            return
        everyone = interaction.guild.default_role
        overwrites = ch.overwrites_for(everyone)
        overwrites.view_channel = None
        await ch.set_permissions(everyone, overwrite=overwrites)
        await interaction.response.send_message("👀 Channel terlihat lagi.", ephemeral=True)

    @discord.ui.button(label="Rename", emoji="✏️", style=discord.ButtonStyle.primary, row=1)
    async def rename(self, interaction: discord.Interaction, _b):
        if not await self._check_owner(interaction):
            return
        await interaction.response.send_modal(RenameModal(self))

    @discord.ui.button(label="Limit", emoji="🔢", style=discord.ButtonStyle.primary, row=1)
    async def limit(self, interaction: discord.Interaction, _b):
        if not await self._check_owner(interaction):
            return
        await interaction.response.send_modal(LimitModal(self))

    @discord.ui.button(label="Claim", emoji="👑", style=discord.ButtonStyle.success, row=1)
    async def claim(self, interaction: discord.Interaction, _b):
        ch = self._channel(interaction)
        if not ch or not interaction.guild:
            return
        if interaction.user not in ch.members:
            await interaction.response.send_message(
                "Kamu harus di voice channel ini buat claim.", ephemeral=True
            )
            return
        owner = interaction.guild.get_member(self.owner_id)
        if owner and owner in ch.members:
            await interaction.response.send_message(
                "❌ Owner masih di voice. Tidak bisa claim.", ephemeral=True
            )
            return
        self.owner_id = interaction.user.id
        _owned_channels.setdefault(interaction.guild.id, {})[ch.id] = interaction.user.id
        await ch.set_permissions(interaction.user, manage_channels=True, connect=True, speak=True)
        await interaction.response.send_message(
            f"👑 {interaction.user.mention} sekarang owner channel ini!", ephemeral=False
        )

    @discord.ui.button(label="Disconnect", emoji="👢", style=discord.ButtonStyle.danger, row=1)
    async def disconnect_user(self, interaction: discord.Interaction, _b):
        if not await self._check_owner(interaction):
            return
        ch = self._channel(interaction)
        if not ch:
            return
        members = [m for m in ch.members if m.id != self.owner_id and not m.bot]
        if not members:
            await interaction.response.send_message("Tidak ada user lain di voice.", ephemeral=True)
            return
        view = DisconnectSelectView(members, self.owner_id)
        await interaction.response.send_message(
            "Pilih user yang mau di-disconnect:", view=view, ephemeral=True
        )


class RenameModal(discord.ui.Modal, title="Ganti nama voice channel"):
    new_name = discord.ui.TextInput(label="Nama baru", max_length=80, placeholder="Misal: Mabar Mobile Legends")

    def __init__(self, view: VoiceControlView):
        super().__init__()
        self.view_ref = view

    async def on_submit(self, interaction: discord.Interaction):
        ch = self.view_ref._channel(interaction)
        if not ch:
            await interaction.response.send_message("Channel hilang.", ephemeral=True)
            return
        try:
            await ch.edit(name=str(self.new_name.value)[:80])
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Gagal: `{e}`", ephemeral=True)
            return
        await interaction.response.send_message(f"✏️ Channel di-rename jadi **{self.new_name.value}**.", ephemeral=True)


class LimitModal(discord.ui.Modal, title="Set user limit"):
    limit = discord.ui.TextInput(label="Maksimal user (0 = unlimited)", max_length=2, placeholder="0-99")

    def __init__(self, view: VoiceControlView):
        super().__init__()
        self.view_ref = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            n = int(str(self.limit.value))
            if not 0 <= n <= 99:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Harus angka 0-99.", ephemeral=True)
            return
        ch = self.view_ref._channel(interaction)
        if not ch:
            return
        try:
            await ch.edit(user_limit=n)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Gagal: `{e}`", ephemeral=True)
            return
        await interaction.response.send_message(f"🔢 Limit di-set ke **{n if n else 'unlimited'}**.", ephemeral=True)


class DisconnectSelectView(discord.ui.View):
    def __init__(self, members: list[discord.Member], owner_id: int):
        super().__init__(timeout=60)
        self.add_item(DisconnectSelect(members, owner_id))


class DisconnectSelect(discord.ui.Select):
    def __init__(self, members: list[discord.Member], owner_id: int):
        opts = [discord.SelectOption(label=m.display_name[:80], value=str(m.id)) for m in members[:25]]
        super().__init__(placeholder="Pilih user...", options=opts, min_values=1, max_values=1)
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Bukan owner.", ephemeral=True)
            return
        if not interaction.guild:
            return
        target = interaction.guild.get_member(int(self.values[0]))
        if not target or not target.voice or not target.voice.channel:
            await interaction.response.send_message("User sudah keluar.", ephemeral=True)
            return
        try:
            await target.move_to(None)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Gagal: `{e}`", ephemeral=True)
            return
        await interaction.response.send_message(f"👢 {target.display_name} di-disconnect.", ephemeral=True)


class VoiceMasterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        if member.bot:
            return
        guild_cfg = await cfg.get_guild(member.guild.id)
        create_id = guild_cfg.get("voicemaster_create_channel")
        cat_id = guild_cfg.get("voicemaster_category")
        if create_id and after.channel and str(after.channel.id) == str(create_id):
            await self._create_channel(member, after.channel, cat_id)
        # Cleanup empty owned channels
        if before.channel and before.channel != after.channel:
            owned = _owned_channels.get(member.guild.id, {})
            if before.channel.id in owned:
                if len([m for m in before.channel.members if not m.bot]) == 0:
                    try:
                        await before.channel.delete(reason="Voicemaster: empty")
                    except discord.HTTPException:
                        pass
                    owned.pop(before.channel.id, None)

    async def _create_channel(
        self,
        member: discord.Member,
        trigger_channel: discord.VoiceChannel,
        category_id: str | None,
    ):
        category = None
        if category_id:
            try:
                cat = member.guild.get_channel(int(category_id))
                if isinstance(cat, discord.CategoryChannel):
                    category = cat
            except (TypeError, ValueError):
                pass
        if category is None:
            category = trigger_channel.category
        try:
            new_ch = await member.guild.create_voice_channel(
                name=f"🔊 {member.display_name}'s room",
                category=category,
                overwrites={
                    member: discord.PermissionOverwrite(manage_channels=True, connect=True, speak=True),
                },
                reason=f"Voicemaster channel for {member}",
            )
        except discord.HTTPException as e:
            log.warning("Failed to create voice channel: %s", e)
            return
        try:
            await member.move_to(new_ch)
        except discord.HTTPException:
            pass
        _owned_channels.setdefault(member.guild.id, {})[new_ch.id] = member.id
        # Send control panel in the voice channel's text chat
        embed = discord.Embed(
            title="🎛️ Voicemaster Control Panel",
            description=(
                f"Owner: {member.mention}\n"
                "Pakai tombol di bawah buat ngatur channel kamu.\n\n"
                "🔒 Lock — Cuma yang udah join yang bisa nyambung\n"
                "👁️ Hide — Sembunyiin dari list channel\n"
                "✏️ Rename — Ganti nama channel\n"
                "🔢 Limit — Set max user\n"
                "👑 Claim — Ambil alih kalau owner pergi\n"
                "👢 Disconnect — Tendang user dari channel"
            ),
            color=discord.Color.from_str("#5865F2"),
        )
        view = VoiceControlView(member.id, new_ch.id)
        try:
            await new_ch.send(embed=embed, view=view)
        except discord.HTTPException:
            pass

    @app_commands.command(
        name="setvoicemaster",
        description="[ADMIN] Set channel 'create voice' & kategori untuk voicemaster.",
    )
    @app_commands.describe(
        create_channel="Voice channel yang akan jadi pemicu (mis. ✗》Create voice)",
        category="Kategori tujuan untuk channel hasil (default: kategori create channel)",
    )
    @app_commands.default_permissions(administrator=True)
    async def setvoicemaster(
        self,
        interaction: discord.Interaction,
        create_channel: discord.VoiceChannel,
        category: discord.CategoryChannel | None = None,
    ):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admin only.", ephemeral=True)
            return
        await cfg.set_guild_field(interaction.guild.id, "voicemaster_create_channel", str(create_channel.id))
        if category:
            await cfg.set_guild_field(interaction.guild.id, "voicemaster_category", str(category.id))
        await interaction.response.send_message(
            f"✅ Voicemaster aktif. Trigger: {create_channel.mention}"
            + (f", kategori: **{category.name}**" if category else ""),
            ephemeral=True,
        )

    @app_commands.command(
        name="createvoice",
        description="[ADMIN] Bikin channel 'Create Voice' & atur voicemaster otomatis.",
    )
    @app_commands.describe(category="Kategori untuk channel pemicu & channel-channel hasilnya")
    @app_commands.default_permissions(administrator=True)
    async def createvoice(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel | None = None,
    ):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admin only.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            ch = await interaction.guild.create_voice_channel(
                name="✗》Create voice",
                category=category,
                reason=f"Voicemaster setup by {interaction.user}",
            )
        except discord.HTTPException as e:
            await interaction.followup.send(f"Gagal bikin channel: `{e}`")
            return
        await cfg.set_guild_field(interaction.guild.id, "voicemaster_create_channel", str(ch.id))
        if category:
            await cfg.set_guild_field(interaction.guild.id, "voicemaster_category", str(category.id))
        await interaction.followup.send(
            f"✅ Channel pemicu dibuat: {ch.mention}. Member yang join akan otomatis dikasih channel sendiri."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceMasterCog(bot))
    log.info("Voicemaster cog loaded.")
