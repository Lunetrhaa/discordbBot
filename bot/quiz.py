import logging
import random

import discord
from discord import app_commands
from discord.ext import commands

import quiz_data
import stats as stats_mod

log = logging.getLogger("bot.quiz")


class QuizView(discord.ui.View):
    def __init__(self, correct: str, choices: list[str], reward: int, game_name: str):
        super().__init__(timeout=30)
        self.correct = correct
        self.reward = reward
        self.game_name = game_name
        self.answered: set[int] = set()
        self.winners: list[str] = []
        for c in choices:
            self.add_item(self._make_btn(c))

    def _make_btn(self, label: str) -> discord.ui.Button:
        btn = discord.ui.Button(label=label[:80], style=discord.ButtonStyle.secondary)

        async def cb(interaction: discord.Interaction):
            if interaction.user.id in self.answered:
                await interaction.response.send_message("Kamu udah jawab!", ephemeral=True)
                return
            self.answered.add(interaction.user.id)
            if label == self.correct:
                self.winners.append(interaction.user.display_name)
                if interaction.guild:
                    await stats_mod.add_points(
                        interaction.guild.id, interaction.user.id, self.reward, self.game_name
                    )
                await interaction.response.send_message(
                    f"✅ Bener! +{self.reward} poin", ephemeral=True
                )
            else:
                if interaction.guild:
                    await stats_mod.add_loss(
                        interaction.guild.id, interaction.user.id, self.game_name
                    )
                await interaction.response.send_message(
                    f"❌ Salah! Jawaban: **{self.correct}**", ephemeral=True
                )

        btn.callback = cb
        return btn

    async def on_timeout(self):
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True


async def _send_quiz(
    interaction: discord.Interaction,
    title: str,
    bank: list[dict],
    reward: int,
    game_name: str,
    color: discord.Color,
    question_label: str = "Pertanyaan",
):
    item = random.choice(bank)
    correct = item["a"]
    choices = item["f"] + [correct]
    random.shuffle(choices)
    view = QuizView(correct, choices, reward, game_name)
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name=question_label, value=item["q"], inline=False)
    embed.set_footer(text=f"30 detik untuk jawab • +{reward} poin")
    await interaction.response.send_message(embed=embed, view=view)
    await view.wait()
    msg = (
        f"🏆 Yang bener: {', '.join(view.winners)}"
        if view.winners
        else f"⏰ Waktu habis. Jawaban: **{correct}**"
    )
    try:
        await interaction.followup.send(msg)
    except discord.HTTPException:
        pass


class QuizCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="tebakbendera", description="Tebak negara dari bendera-nya.")
    async def tebakbendera(self, interaction: discord.Interaction):
        await _send_quiz(
            interaction, "🌏 Tebak Bendera", quiz_data.FLAGS, 5,
            "tebakbendera", discord.Color.blue(), "Bendera",
        )

    @app_commands.command(name="tebakkpop", description="Tebak grup K-Pop dari list member.")
    async def tebakkpop(self, interaction: discord.Interaction):
        await _send_quiz(
            interaction, "🎤 Tebak Grup K-Pop", quiz_data.KPOP, 10,
            "tebakkpop", discord.Color.magenta(), "Member-nya",
        )

    @app_commands.command(name="tebakkata", description="Tebak kata dari definisinya (Bahasa Indonesia).")
    async def tebakkata(self, interaction: discord.Interaction):
        await _send_quiz(
            interaction, "📖 Tebak Kata", quiz_data.WORDS, 10,
            "tebakkata", discord.Color.orange(), "Definisi",
        )

    @app_commands.command(name="tebakkota", description="Tebak ibu kota negara.")
    async def tebakkota(self, interaction: discord.Interaction):
        await _send_quiz(
            interaction, "🏙️ Tebak Ibu Kota", quiz_data.CAPITALS, 5,
            "tebakkota", discord.Color.teal(), "Negara",
        )

    @app_commands.command(name="tebakhewan", description="Tebak hewan dari deskripsi.")
    async def tebakhewan(self, interaction: discord.Interaction):
        await _send_quiz(
            interaction, "🐾 Tebak Hewan", quiz_data.ANIMALS, 5,
            "tebakhewan", discord.Color.green(), "Deskripsi",
        )

    @app_commands.command(name="tebakbahasa", description="Tebak bahasa dari sapaannya.")
    async def tebakbahasa(self, interaction: discord.Interaction):
        await _send_quiz(
            interaction, "💬 Tebak Bahasa", quiz_data.GREETINGS, 5,
            "tebakbahasa", discord.Color.purple(), "Sapaan",
        )

    @app_commands.command(name="tebakwarna", description="Tebak nama warna dari kode hex.")
    async def tebakwarna(self, interaction: discord.Interaction):
        await _send_quiz(
            interaction, "🎨 Tebak Warna", quiz_data.COLORS, 5,
            "tebakwarna", discord.Color.gold(), "Kode HEX",
        )

    @app_commands.command(name="tebakemoji", description="Tebak film/karakter dari emoji.")
    async def tebakemoji(self, interaction: discord.Interaction):
        await _send_quiz(
            interaction, "🎬 Tebak Emoji", quiz_data.EMOJI_PUZZLES, 10,
            "tebakemoji", discord.Color.yellow(), "Emoji",
        )

    @app_commands.command(name="tebaktahun", description="Tebak tahun peristiwa sejarah.")
    async def tebaktahun(self, interaction: discord.Interaction):
        await _send_quiz(
            interaction, "🕰️ Tebak Tahun", quiz_data.YEARS, 10,
            "tebaktahun", discord.Color.dark_orange(), "Peristiwa",
        )

    @app_commands.command(name="tebakkarakter", description="Tebak karakter anime/film dari deskripsi.")
    async def tebakkarakter(self, interaction: discord.Interaction):
        await _send_quiz(
            interaction, "🦸 Tebak Karakter", quiz_data.CHARACTERS, 10,
            "tebakkarakter", discord.Color.dark_purple(), "Deskripsi",
        )

    @app_commands.command(name="tebaklagu", description="Tebak lagu dari potongan liriknya.")
    async def tebaklagu(self, interaction: discord.Interaction):
        await _send_quiz(
            interaction, "🎵 Tebak Lagu", quiz_data.LYRICS, 10,
            "tebaklagu", discord.Color.fuchsia(), "Lirik",
        )

    @app_commands.command(name="stats", description="Lihat statistik & poin kamu atau orang lain.")
    @app_commands.describe(user="User yang stats-nya mau dilihat (kosongin = stats kamu)")
    async def stats_cmd(
        self, interaction: discord.Interaction, user: discord.Member | None = None
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "Cuma bisa di server.", ephemeral=True
            )
            return
        target = user or interaction.user
        s = await stats_mod.get_stats(interaction.guild.id, target.id)
        rank, total = await stats_mod.rank_of(interaction.guild.id, target.id)
        played = s.get("played", 0)
        wins = s.get("wins", 0)
        losses = s.get("losses", 0)
        winrate = f"{(wins / played * 100):.1f}%" if played else "—"
        embed = discord.Embed(
            title=f"📊 Stats — {target.display_name}",
            color=discord.Color.blurple(),
        )
        if isinstance(target, (discord.Member, discord.User)):
            embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🏆 Poin", value=f"**{s.get('points', 0)}**", inline=True)
        embed.add_field(
            name="🥇 Peringkat",
            value=f"**#{rank}** dari {total}" if rank else "Belum ranking",
            inline=True,
        )
        embed.add_field(name="🎮 Dimainkan", value=str(played), inline=True)
        embed.add_field(name="✅ Menang", value=str(wins), inline=True)
        embed.add_field(name="❌ Kalah", value=str(losses), inline=True)
        embed.add_field(name="📈 Win rate", value=winrate, inline=True)
        games = s.get("games", {})
        if games:
            top_games = sorted(games.items(), key=lambda x: -x[1])[:5]
            embed.add_field(
                name="Top game dimainkan",
                value="\n".join(f"`{g}` — {n}x" for g, n in top_games),
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Top 10 player berdasarkan poin di server ini.")
    async def leaderboard(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Cuma bisa di server.", ephemeral=True)
            return
        ranked = await stats_mod.top(interaction.guild.id, 10)
        if not ranked:
            await interaction.response.send_message("Belum ada yang main game di sini.")
            return
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, (uid, pts) in enumerate(ranked):
            try:
                member = interaction.guild.get_member(int(uid)) or await self.bot.fetch_user(int(uid))
                name = member.display_name if isinstance(member, discord.Member) else member.name
            except (discord.NotFound, ValueError):
                name = f"User#{uid}"
            prefix = medals[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{prefix} **{name}** — {pts} poin")
        embed = discord.Embed(
            title=f"🏆 Leaderboard — {interaction.guild.name}",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="quizlist", description="Daftar semua tebak-tebakan yang ada.")
    async def quizlist(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🧠 Tebak-tebakan",
            description="Semua game ngasih poin yang masuk ke `/stats` & `/leaderboard`.",
            color=discord.Color.blurple(),
        )
        items = [
            ("/tebakbendera", "Tebak negara dari bendera (5 poin)"),
            ("/tebakkpop", "Tebak grup K-Pop dari member (10 poin)"),
            ("/tebakkata", "Tebak kata dari definisi (10 poin)"),
            ("/tebakkota", "Tebak ibu kota negara (5 poin)"),
            ("/tebakhewan", "Tebak hewan dari deskripsi (5 poin)"),
            ("/tebakbahasa", "Tebak bahasa dari sapaan (5 poin)"),
            ("/tebakwarna", "Tebak warna dari kode HEX (5 poin)"),
            ("/tebakemoji", "Tebak film dari emoji (10 poin)"),
            ("/tebaktahun", "Tebak tahun peristiwa (10 poin)"),
            ("/tebakkarakter", "Tebak karakter anime/film (10 poin)"),
            ("/tebaklagu", "Tebak lagu dari lirik (10 poin)"),
            ("/trivia", "Trivia umum (10 poin)"),
        ]
        for name, desc in items:
            embed.add_field(name=name, value=desc, inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(QuizCog(bot))
    log.info("Quiz cog loaded.")
