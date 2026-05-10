import ast
import logging
import operator
import random
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands

from . import config as cfg
from .import stats as stats_mod

log = logging.getLogger("bot.social")

JAKARTA = timezone(timedelta(hours=7))

# Roblox marketplace fee = 30%, dev gets 70%.
ROBUX_DEV_RATE = 0.70

# Special love handles (case-insensitive substring match on display_name and username).
SPECIAL_HANDLES = ["jaa", "fey"]


def _normalize_name(name: str) -> str:
    """Lowercase + strip stylized fonts to plain ASCII letters where possible."""
    import unicodedata
    s = unicodedata.normalize("NFKD", name)
    return "".join(c for c in s.lower() if c.isalnum())


def _is_special(member: discord.abc.User) -> bool:
    candidates = [
        getattr(member, "display_name", "") or "",
        getattr(member, "name", "") or "",
        getattr(member, "global_name", "") or "",
    ]
    norm = " ".join(_normalize_name(c) for c in candidates)
    return any(h in norm for h in SPECIAL_HANDLES)


def _alpha_distance(a: str, b: str) -> int:
    if not a or not b:
        return 13
    return abs(ord(a[0]) - ord(b[0]))


def _love_percent(a: discord.abc.User, b: discord.abc.User) -> int:
    if a.id == b.id:
        return 100
    sa, sb = _is_special(a), _is_special(b)
    seed = (a.id + b.id) % 10_000_000
    rng = random.Random(seed)
    if sa and sb:
        return 100
    if sa or sb:
        return rng.randint(90, 100)
    na = _normalize_name(getattr(a, "display_name", "") or a.name)
    nb = _normalize_name(getattr(b, "display_name", "") or b.name)
    dist = _alpha_distance(na, nb)
    base = max(0, 100 - dist * 5)
    jitter = rng.randint(-15, 15)
    pct = max(5, min(99, base + jitter))
    return pct


def _love_bar(pct: int) -> str:
    filled = round(pct / 5)
    return "💖" * filled + "🤍" * (20 - filled)


SAFE_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
SAFE_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
SAFE_FUNCS = {
    "abs": abs, "round": round, "min": min, "max": max,
    "sqrt": lambda x: x ** 0.5,
    "log": __import__("math").log,
    "log10": __import__("math").log10,
    "sin": __import__("math").sin,
    "cos": __import__("math").cos,
    "tan": __import__("math").tan,
    "pi": __import__("math").pi,
    "e": __import__("math").e,
}


def safe_eval(expr: str):
    """Evaluate a math expression safely. No name lookup beyond SAFE_FUNCS."""
    tree = ast.parse(expr, mode="eval")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Hanya angka.")
        if isinstance(node, ast.BinOp) and type(node.op) in SAFE_BINOPS:
            return SAFE_BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_UNARY:
            return SAFE_UNARY[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.Name):
            if node.id in SAFE_FUNCS:
                return SAFE_FUNCS[node.id]
            raise ValueError(f"Tidak dikenal: {node.id}")
        if isinstance(node, ast.Call):
            fn = _eval(node.func)
            args = [_eval(a) for a in node.args]
            if not callable(fn):
                raise ValueError("Bukan fungsi.")
            return fn(*args)
        raise ValueError("Ekspresi tidak diizinkan.")

    return _eval(tree)


def fmt_idr(n: float) -> str:
    return f"Rp {n:,.0f}".replace(",", ".")


class SocialCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="love", description="Cek tingkat cinta antara dua orang.")
    @app_commands.describe(
        user1="Orang pertama",
        user2="Orang kedua (default: kamu)",
    )
    async def love(
        self,
        interaction: discord.Interaction,
        user1: discord.Member,
        user2: discord.Member | None = None,
    ):
        partner = user2 or interaction.user
        pct = _love_percent(user1, partner)
        if pct >= 90:
            verdict = "💕 Soulmate banget! Jodoh nih."
        elif pct >= 70:
            verdict = "❤️ Cocok parah, lanjut yuk!"
        elif pct >= 50:
            verdict = "💛 Lumayan, butuh effort lebih."
        elif pct >= 30:
            verdict = "🧡 Hmm... mendingan temenan dulu."
        else:
            verdict = "💔 Friendzone abadi."
        heart = "💕" if pct == 100 else "❤️"
        embed = discord.Embed(
            title=f"{heart} Love Meter {heart}",
            description=f"{user1.mention} 💞 {partner.mention}",
            color=discord.Color.from_str("#FF4D6D"),
        )
        embed.add_field(name="Tingkat cinta", value=f"**{pct}%**", inline=False)
        embed.add_field(name="Bar", value=_love_bar(pct), inline=False)
        embed.add_field(name="Verdict", value=verdict, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dailyclaim", description="Klaim bonus poin harian (1x sehari).")
    async def dailyclaim(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Cuma di server.", ephemeral=True)
            return
        today = datetime.now(JAKARTA).strftime("%Y-%m-%d")
        base = random.randint(50, 150)
        ok, streak, total = await stats_mod.claim_daily(
            interaction.guild.id, interaction.user.id, today, base
        )
        if not ok:
            embed = discord.Embed(
                title="⏳ Sudah klaim hari ini",
                description="Balik lagi besok ya! Streak kamu sekarang: "
                            f"**{streak} hari** 🔥",
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        bonus = total - base
        embed = discord.Embed(
            title="🎁 Daily Claim",
            description=f"Selamat {interaction.user.mention}! Kamu dapat **{total} poin**.",
            color=discord.Color.green(),
        )
        embed.add_field(name="Base", value=f"{base} poin", inline=True)
        embed.add_field(name="Streak bonus", value=f"+{bonus} poin", inline=True)
        embed.add_field(name="🔥 Streak", value=f"{streak} hari", inline=True)
        embed.set_footer(text="Streak naik tiap hari berturut-turut, max bonus +175 setelah 7 hari.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="calc", description="Kalkulator: hitung ekspresi matematika.")
    @app_commands.describe(expr="Contoh: 1500*30 + 250000/5, atau sqrt(144)")
    async def calc(self, interaction: discord.Interaction, expr: str):
        try:
            result = safe_eval(expr)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: `{e}`", ephemeral=True)
            return
        if isinstance(result, float):
            display = f"{result:,.6g}"
        else:
            display = f"{result:,}"
        embed = discord.Embed(title="🧮 Kalkulator", color=discord.Color.blue())
        embed.add_field(name="Ekspresi", value=f"`{expr[:200]}`", inline=False)
        embed.add_field(name="Hasil", value=f"**{display}**", inline=False)
        if isinstance(result, (int, float)) and result >= 1000:
            embed.add_field(name="Sebagai Rupiah", value=fmt_idr(float(result)), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="robux", description="Hitung Robux setelah pajak Roblox 30%.")
    @app_commands.describe(
        amount="Jumlah Robux di gamepass (sebelum pajak)",
        rate_per_robux="Harga 1 Robux dalam Rupiah (opsional, default 130)",
    )
    async def robux(
        self,
        interaction: discord.Interaction,
        amount: int,
        rate_per_robux: float | None = None,
    ):
        if amount < 1:
            await interaction.response.send_message("Minimal 1 Robux.", ephemeral=True)
            return
        rate = rate_per_robux if rate_per_robux and rate_per_robux > 0 else 130.0
        net = int(amount * ROBUX_DEV_RATE)  # Roblox rounds down
        tax = amount - net
        idr_net = net * rate
        idr_gross = amount * rate
        # Reverse: how much to set price to receive `amount` net?
        gross_for_amount = -(-amount * 100 // 70)  # ceil division
        embed = discord.Embed(
            title="💰 Kalkulator Robux",
            color=discord.Color.from_str("#00b06f"),
        )
        embed.add_field(name="Harga gamepass", value=f"**{amount:,} R$**", inline=True)
        embed.add_field(name="Pajak Roblox (30%)", value=f"−{tax:,} R$", inline=True)
        embed.add_field(name="Kamu terima (netto)", value=f"**{net:,} R$**", inline=True)
        embed.add_field(name=f"Estimasi Rupiah (Rp {rate:,.0f}/R$)", value=fmt_idr(idr_net), inline=False)
        embed.add_field(
            name=f"Mau dapat {amount:,} R$ bersih?",
            value=f"Set harga gamepass: **{gross_for_amount:,} R$** ({fmt_idr(gross_for_amount * rate)})",
            inline=False,
        )
        embed.set_footer(text="Catatan: Roblox membulatkan ke bawah, jadi pendapatan asli mungkin sedikit kurang.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="confess", description="Kirim pesan anonim ke channel confess.")
    @app_commands.describe(text="Isi pengakuan kamu")
    async def confess(self, interaction: discord.Interaction, text: str):
        if not interaction.guild:
            await interaction.response.send_message("Cuma di server.", ephemeral=True)
            return
        guild_cfg = await cfg.get_guild(interaction.guild.id)
        chan_id = guild_cfg.get("confess_channel")
        if not chan_id:
            await interaction.response.send_message(
                "Channel confess belum di-setup. Admin bisa atur via `/setconfess`.",
                ephemeral=True,
            )
            return
        chan = self.bot.get_channel(int(chan_id))
        if not isinstance(chan, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("Channel confess tidak valid.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🤫 Anonymous Confession",
            description=text[:4000],
            color=discord.Color.dark_purple(),
        )
        embed.set_footer(text="Dikirim secara anonim • /confess")
        try:
            await chan.send(embed=embed)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Gagal kirim: `{e}`", ephemeral=True)
            return
        await interaction.response.send_message("✅ Pengakuan kamu udah dikirim anonim.", ephemeral=True)

    @app_commands.command(name="setconfess", description="[ADMIN] Set channel untuk /confess.")
    @app_commands.describe(channel="Channel tujuan confession")
    @app_commands.default_permissions(administrator=True)
    async def setconfess(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admin only.", ephemeral=True)
            return
        await cfg.set_guild_field(interaction.guild.id, "confess_channel", str(channel.id))
        await interaction.response.send_message(
            f"✅ Channel confess di-set ke {channel.mention}.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SocialCog(bot))
    log.info("Social cog loaded.")
