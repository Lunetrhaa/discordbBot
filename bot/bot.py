import os
import random
import logging

import discord
from discord import app_commands
from discord.ext import commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("bot")

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN environment variable is not set.")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="m/", intents=intents, help_command=None)


@bot.event
async def setup_hook():
    from music import setup as setup_music
    await setup_music(bot)


TRUTHS = [
    "Apa hal paling memalukan yang pernah kamu lakukan setahun terakhir?",
    "Rahasia apa yang belum pernah kamu ceritakan ke siapa pun di server ini?",
    "Siapa di server ini yang paling kamu percaya untuk pegang HP-mu seharian?",
    "Mimpi paling aneh yang pernah kamu alami akhir-akhir ini apa?",
    "Kebohongan terburuk apa yang pernah kamu katakan ke orang tuamu?",
    "Apa hal yang sebenarnya kamu nggak suka tapi kamu pura-pura suka biar bisa nyambung?",
    "Apa yang terakhir kamu cari di HP-mu?",
    "Hal kekanak-kanakan apa yang masih sering kamu lakukan?",
    "Bakat apa yang kamu harap kamu punya?",
    "Pernah nggak nyontek pas ulangan? Cerita dong!",
    "Ketakutan paling nggak masuk akal yang kamu punya apa?",
    "Hadiah terburuk yang pernah kamu terima apa?",
    "Apa hal yang pernah kamu lakukan yang nggak bakal kamu ceritain ke orang tuamu?",
    "Siapa cinta pertamamu?",
    "Masalah paling besar yang pernah kamu buat apa?",
    "Kebiasaan apa yang kamu malu sendiri kalau orang tahu?",
    "Opini paling kontroversialmu soal makanan apa?",
    "Kalau harus hapus satu aplikasi di HP-mu selamanya, aplikasi apa?",
    "Pesan terakhir yang kamu kirim ke siapa dan isinya apa?",
    "Berapa lama paling lama kamu pernah nggak mandi?",
    "Crush rahasia kamu di server ini siapa?",
    "Pernah nggak suka sama temennya temen sendiri?",
    "Kapan terakhir kali kamu nangis dan kenapa?",
    "Hal paling memalukan di galeri HP-mu apa?",
    "Pernah nggak ngomongin orang di server ini di belakangnya?",
]

DARES = [
    "Kirim foto ke-5 dari galeri HP-mu ke channel ini.",
    "Ngomong pakai aksen Inggris untuk 3 pesan berikutnya.",
    "DM seseorang di server ini sebuah pujian sekarang juga.",
    "Ketik pesan berikutnya dengan mata tertutup — nggak boleh diedit.",
    "Ganti nickname-mu jadi apa pun yang dipilih orang berikutnya selama 10 menit.",
    "Posting meme terakhir yang kamu simpan.",
    "Kirim voice note nyanyi reff lagu apa pun.",
    "Cerita lelucon. Kalau nggak ada yang react, dare lagi.",
    "Ketik abjad A-Z pakai emoji semua.",
    "Set status Discord-mu jadi 'Aku kalah dare' selama 1 jam.",
    "Ceritain dengan detail satu foto masa kecil yang memalukan.",
    "Push-up 10 kali dan posting bukti video atau foto.",
    "Kirim screenshot home screen HP-mu.",
    "Ngomong kayak bajak laut selama 5 menit ke depan.",
    "Baca pesan terakhirmu pakai suara dramatis (kirim voice note).",
    "Ganti foto profilmu jadi karakter kartun selama 24 jam.",
    "Buat puisi 2 baris tentang orang di atas chat.",
    "Kirim lagu terakhir yang kamu dengerin.",
    "Eja namamu terbalik dan pakai jadi nickname selama 10 menit.",
    "Posting selfie dengan ekspresi paling konyol yang kamu bisa.",
    "Tag random 3 orang di server ini dan bilang kenapa kamu suka mereka.",
    "Tiru suara hewan favoritmu lewat voice note.",
    "Kirim emoji terakhir yang kamu pakai 5 kali berturut-turut.",
    "Ceritain crush pertamamu dalam 1 kalimat.",
    "Posting screenshot percakapan WA paling random kamu (sensor nama).",
]


class TruthOrDareView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.message: discord.Message | None = None

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    async def _respond(self, interaction: discord.Interaction, kind: str):
        if kind == "truth":
            prompt = random.choice(TRUTHS)
            color = discord.Color.blue()
            title = "Truth"
        else:
            prompt = random.choice(DARES)
            color = discord.Color.red()
            title = "Dare"
        embed = discord.Embed(title=title, description=prompt, color=color)
        embed.set_footer(text=f"Untuk {interaction.user.display_name}")
        view = TruthOrDareView()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @discord.ui.button(label="Truth", style=discord.ButtonStyle.primary, emoji="\U0001F914")
    async def truth_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._respond(interaction, "truth")

    @discord.ui.button(label="Dare", style=discord.ButtonStyle.danger, emoji="\U0001F525")
    async def dare_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._respond(interaction, "dare")

    @discord.ui.button(label="Random", style=discord.ButtonStyle.secondary, emoji="\U0001F3B2")
    async def random_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._respond(interaction, random.choice(["truth", "dare"]))


@bot.event
async def on_ready():
    log.info("Logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "?")
    log.info("Connected to %d guild(s).", len(bot.guilds))
    activity = discord.Game(name="Lunethra.gg | /help")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            log.info("Synced %d slash command(s) to guild %s.", len(synced), guild.name)
        except Exception:
            log.exception("Failed to sync slash commands to guild %s", guild.name)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "Kamu nggak punya izin untuk pakai command ini."
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"Pelan-pelan, coba lagi dalam {error.retry_after:.1f}s."
    else:
        log.exception("Unhandled app command error", exc_info=error)
        msg = "Ada yang error pas jalanin command itu."
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(name="help", description="Tampilkan daftar command.")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Bot Commands",
        description="Semua command pakai prefix `/`",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="/ping", value="Cek latency bot.", inline=False)
    embed.add_field(name="/hello", value="Sapaan ramah.", inline=False)
    embed.add_field(name="/say", value="Bot ngulang pesan kamu.", inline=False)
    embed.add_field(name="/roll", value="Lempar dadu (mis. `2d6`). Default `1d6`.", inline=False)
    embed.add_field(name="/flip", value="Lempar koin.", inline=False)
    embed.add_field(name="/choose", value="Pilih satu opsi acak (pisahkan dengan koma).", inline=False)
    embed.add_field(name="/avatar", value="Tampilkan avatar user.", inline=False)
    embed.add_field(name="/userinfo", value="Info user.", inline=False)
    embed.add_field(name="/serverinfo", value="Info server.", inline=False)
    embed.add_field(name="/clear", value="Hapus n pesan terakhir (perlu izin Manage Messages).", inline=False)
    embed.add_field(name="/tod", value="Mulai game Truth or Dare dengan tombol.", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ping", description="Cek latency bot.")
async def ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! `{latency_ms}ms`")


@bot.tree.command(name="hello", description="Sapaan ramah.")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hai {interaction.user.mention}!")


@bot.tree.command(name="say", description="Bot ngulang pesan kamu.")
@app_commands.describe(text="Pesan yang mau diulang")
async def say(interaction: discord.Interaction, text: str):
    await interaction.response.send_message(text)


@bot.tree.command(name="roll", description="Lempar dadu, format NdN (mis. 2d6).")
@app_commands.describe(dice="Format dadu, default 1d6")
async def roll(interaction: discord.Interaction, dice: str = "1d6"):
    try:
        count_str, sides_str = dice.lower().split("d", 1)
        count = int(count_str) if count_str else 1
        sides = int(sides_str)
        if not (1 <= count <= 100) or not (2 <= sides <= 1000):
            raise ValueError
    except ValueError:
        await interaction.response.send_message(
            "Pakai format `NdN`, mis. `2d6`. Batas: 1–100 dadu, 2–1000 sisi.",
            ephemeral=True,
        )
        return
    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls)
    detail = ", ".join(str(r) for r in rolls)
    await interaction.response.send_message(
        f"{interaction.user.mention} dapet **{total}** ({detail})"
    )


@bot.tree.command(name="flip", description="Lempar koin.")
async def flip(interaction: discord.Interaction):
    await interaction.response.send_message(random.choice(["Heads", "Tails"]))


@bot.tree.command(name="choose", description="Pilih satu opsi acak.")
@app_commands.describe(options="Opsi yang dipisahkan dengan koma, mis. `pizza, taco, sushi`")
async def choose(interaction: discord.Interaction, options: str):
    parts = [p.strip() for p in options.split(",") if p.strip()]
    if len(parts) < 2:
        await interaction.response.send_message(
            "Kasih minimal dua opsi (pisahkan dengan koma).", ephemeral=True
        )
        return
    await interaction.response.send_message(f"Aku pilih: **{random.choice(parts)}**")


@bot.tree.command(name="avatar", description="Tampilkan avatar user.")
@app_commands.describe(user="User yang mau dilihat avatarnya (default: kamu)")
async def avatar(interaction: discord.Interaction, user: discord.Member | None = None):
    target = user or interaction.user
    embed = discord.Embed(title=f"Avatar {target.display_name}", color=discord.Color.blurple())
    embed.set_image(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="userinfo", description="Info user.")
@app_commands.describe(user="User yang mau dilihat (default: kamu)")
async def userinfo(interaction: discord.Interaction, user: discord.Member | None = None):
    target = user or interaction.user
    embed = discord.Embed(title=str(target), color=discord.Color.green())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="ID", value=str(target.id), inline=False)
    embed.add_field(name="Created", value=target.created_at.strftime("%Y-%m-%d %H:%M UTC"), inline=False)
    if isinstance(target, discord.Member) and target.joined_at:
        embed.add_field(name="Joined", value=target.joined_at.strftime("%Y-%m-%d %H:%M UTC"), inline=False)
        roles = [r.mention for r in target.roles if r.name != "@everyone"]
        if roles:
            embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="serverinfo", description="Info server ini.")
async def serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    if g is None:
        await interaction.response.send_message("Command ini cuma bisa dipakai di server.", ephemeral=True)
        return
    embed = discord.Embed(title=g.name, color=discord.Color.gold())
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.add_field(name="ID", value=str(g.id), inline=False)
    embed.add_field(name="Owner", value=str(g.owner), inline=False)
    embed.add_field(name="Members", value=str(g.member_count), inline=True)
    embed.add_field(name="Channels", value=str(len(g.channels)), inline=True)
    embed.add_field(name="Roles", value=str(len(g.roles)), inline=True)
    embed.add_field(name="Created", value=g.created_at.strftime("%Y-%m-%d"), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="clear", description="Hapus n pesan terakhir.")
@app_commands.describe(amount="Jumlah pesan (1-100)")
@app_commands.default_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
    channel = interaction.channel
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        await interaction.response.send_message("Cuma bisa di text channel.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await channel.purge(limit=amount)
    await interaction.followup.send(f"Berhasil hapus {len(deleted)} pesan.", ephemeral=True)


@bot.tree.command(name="tod", description="Mulai game Truth or Dare dengan tombol.")
async def tod(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Truth or Dare",
        description="Pilih nasibmu. Klik salah satu tombol di bawah.",
        color=discord.Color.purple(),
    )
    embed.add_field(name="Truth", value="Jawab pertanyaan jujur.", inline=True)
    embed.add_field(name="Dare", value="Selesaikan tantangan.", inline=True)
    embed.add_field(name="Random", value="Biar takdir yang pilih.", inline=True)
    embed.set_footer(text=f"Dimulai oleh {interaction.user.display_name}")
    view = TruthOrDareView()
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()


if __name__ == "__main__":
    bot.run(TOKEN, log_handler=None)
