import asyncio
import html as html_lib
import json
import logging
import random
import urllib.parse
import urllib.request

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("bot.games")


WYR = [
    ("Punya kekuatan terbang", "Punya kekuatan tak terlihat"),
    ("Hidup tanpa internet selamanya", "Hidup tanpa musik selamanya"),
    ("Bisa baca pikiran orang", "Bisa lihat masa depan kamu sendiri"),
    ("Selalu kepanasan", "Selalu kedinginan"),
    ("Punya pacar yang ganteng/cantik tapi pelit", "Pacar biasa tapi loyal banget"),
    ("Liburan ke pantai selamanya", "Tinggal di pegunungan selamanya"),
    ("Bisa bahasa semua negara", "Bisa main semua alat musik"),
    ("Jadi terkenal tapi nggak kaya", "Kaya tapi nggak ada yang kenal"),
    ("Hilang ingatan selama 5 tahun", "Tahu kapan kamu meninggal"),
    ("Makan pedas tiap hari", "Makan manis tiap hari"),
    ("Tinggal di kota", "Tinggal di desa"),
    ("Punya rumah mewah tapi sendiri", "Rumah kecil rame-rame sama keluarga"),
    ("Nggak boleh pakai HP 1 minggu", "Nggak boleh tidur 3 hari"),
    ("Jadi pemain bola terkenal", "Jadi musisi terkenal"),
    ("Pacaran sama orang yang lebih tua 10 tahun", "Pacaran sama orang yang lebih muda 10 tahun"),
    ("Hidup tanpa kopi", "Hidup tanpa teh"),
    ("Punya 100 teman tapi semua jauh", "Punya 1 sahabat sejati"),
    ("Jadi pintar banget", "Jadi paling cantik/ganteng se-server"),
    ("Liburan gratis tiap bulan", "Gaji 2x lipat tapi kerja terus"),
    ("Selalu telat 30 menit", "Selalu datang 1 jam lebih awal"),
]

NHIE = [
    "...stalk Instagram mantan tengah malam.",
    "...nangis karena drama Korea.",
    "...ketiduran di kelas atau meeting.",
    "...kentut di lift terus pura-pura nggak tau.",
    "...screenshot chat orang terus dikirim ke temen.",
    "...bohong soal umur biar dapet diskon.",
    "...nyanyi keras di kamar mandi sampai ketauan.",
    "...lupa nama orang yang udah kenal lama.",
    "...beli sesuatu cuma karena lagi sale, padahal nggak butuh.",
    "...ngintip jawaban temen pas ulangan.",
    "...nge-like foto crush dari tahun lalu nggak sengaja.",
    "...ngomong sendiri di depan cermin.",
    "...ketawa sendiri karena ingat hal random.",
    "...pura-pura sibuk biar nggak diajak jalan.",
    "...nge-stalk profile sendiri lewat akun lain.",
    "...lupa mandi sehari penuh.",
    "...makan sambil baring di kasur sampai tumpah.",
    "...nyaru jadi orang lain di chat.",
    "...nangis pas nonton iklan.",
    "...sengaja telat balas chat biar keliatan sibuk.",
]

THIS_OR_THAT = [
    ("Pizza", "Burger"),
    ("Kopi", "Teh"),
    ("Pagi", "Malam"),
    ("Anjing", "Kucing"),
    ("Pantai", "Gunung"),
    ("iPhone", "Android"),
    ("Marvel", "DC"),
    ("Manis", "Asin"),
    ("Film", "Series"),
    ("Buku", "Podcast"),
    ("PC", "Console"),
    ("Indomie", "Mie Sedaap"),
    ("Sneakers", "Sandal"),
    ("Hujan", "Salju"),
    ("Online", "Offline"),
    ("Cash", "QRIS"),
    ("Ngopi sendiri", "Ngopi rame-rame"),
    ("Naik motor", "Naik mobil"),
    ("Spotify", "YouTube Music"),
    ("Halloween", "Valentine"),
]

EIGHTBALL = [
    "Pasti.", "Sangat mungkin.", "Tanpa keraguan.", "Ya.", "Bisa diandalkan.",
    "Sepertinya iya.", "Tanda-tandanya menunjuk ke iya.", "Coba lagi nanti.",
    "Tanyakan lagi nanti.", "Lebih baik nggak usah dijawab sekarang.",
    "Nggak bisa diprediksi.", "Konsentrasi & tanya lagi.", "Jangan harap.",
    "Jawabanku: tidak.", "Sumberku bilang tidak.", "Kelihatannya nggak baik.",
    "Sangat diragukan.",
]

SCRAMBLE_WORDS = [
    "kucing", "rumah", "pelangi", "matahari", "komputer", "laptop", "internet",
    "musik", "gitar", "mobil", "sepeda", "pesawat", "indonesia", "jakarta",
    "bandung", "surabaya", "bahasa", "discord", "server", "pemrograman",
    "python", "javascript", "android", "windows", "kemerdekaan", "merdeka",
    "pendidikan", "perpustakaan", "matematika", "olahraga", "sepakbola",
    "bulutangkis", "renang", "memasak", "lukisan", "fotografi",
]


def shuffle_word(word: str) -> str:
    chars = list(word)
    while True:
        random.shuffle(chars)
        scrambled = "".join(chars)
        if scrambled != word:
            return scrambled


def fetch_trivia() -> dict | None:
    try:
        url = "https://opentdb.com/api.php?amount=1&type=multiple"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("response_code") == 0 and data.get("results"):
            r = data["results"][0]
            return {
                "category": html_lib.unescape(r["category"]),
                "difficulty": r["difficulty"],
                "question": html_lib.unescape(r["question"]),
                "correct": html_lib.unescape(r["correct_answer"]),
                "incorrect": [html_lib.unescape(a) for a in r["incorrect_answers"]],
            }
    except Exception:
        log.exception("Trivia fetch failed")
    return None


class TriviaView(discord.ui.View):
    def __init__(self, correct: str, choices: list[str], asker: discord.abc.User):
        super().__init__(timeout=30)
        self.correct = correct
        self.asker = asker
        self.answered: set[int] = set()
        self.winners: list[str] = []
        for i, c in enumerate(choices):
            self.add_item(self._make_btn(c, i))

    def _make_btn(self, label: str, idx: int) -> discord.ui.Button:
        btn = discord.ui.Button(label=label[:80], style=discord.ButtonStyle.secondary)

        async def cb(interaction: discord.Interaction):
            import stats as stats_mod
            if interaction.user.id in self.answered:
                await interaction.response.send_message("Kamu udah jawab!", ephemeral=True)
                return
            self.answered.add(interaction.user.id)
            if label == self.correct:
                self.winners.append(interaction.user.display_name)
                if interaction.guild:
                    await stats_mod.add_points(
                        interaction.guild.id, interaction.user.id, 10, "trivia"
                    )
                await interaction.response.send_message("✅ Bener! +10 poin", ephemeral=True)
            else:
                if interaction.guild:
                    await stats_mod.add_loss(
                        interaction.guild.id, interaction.user.id, "trivia"
                    )
                await interaction.response.send_message(f"❌ Salah! Jawaban: **{self.correct}**", ephemeral=True)

        btn.callback = cb
        return btn

    async def on_timeout(self):
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True


class RPSView(discord.ui.View):
    EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
    BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

    def __init__(self, user: discord.abc.User):
        super().__init__(timeout=30)
        self.user = user

    async def _handle(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Ini bukan game kamu!", ephemeral=True)
            return
        bot_pick = random.choice(list(self.BEATS.keys()))
        if choice == bot_pick:
            result = "Seri!"
        elif self.BEATS[choice] == bot_pick:
            result = "Kamu menang!"
        else:
            result = "Bot menang!"
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        await interaction.response.edit_message(
            content=f"{self.EMOJI[choice]} vs {self.EMOJI[bot_pick]} — **{result}**",
            view=self,
        )

    @discord.ui.button(label="Rock", emoji="🪨", style=discord.ButtonStyle.secondary)
    async def rock(self, i: discord.Interaction, _b): await self._handle(i, "rock")

    @discord.ui.button(label="Paper", emoji="📄", style=discord.ButtonStyle.secondary)
    async def paper(self, i: discord.Interaction, _b): await self._handle(i, "paper")

    @discord.ui.button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.secondary)
    async def scissors(self, i: discord.Interaction, _b): await self._handle(i, "scissors")


class WYRView(discord.ui.View):
    def __init__(self, opt_a: str, opt_b: str):
        super().__init__(timeout=120)
        self.opt_a = opt_a
        self.opt_b = opt_b
        self.votes: dict[int, str] = {}
        self.message: discord.Message | None = None

    async def _vote(self, interaction: discord.Interaction, side: str):
        self.votes[interaction.user.id] = side
        a = sum(1 for v in self.votes.values() if v == "a")
        b = sum(1 for v in self.votes.values() if v == "b")
        await interaction.response.send_message(
            f"Voting tercatat. Skor: A `{a}` — B `{b}`", ephemeral=True
        )

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary)
    async def a_btn(self, i: discord.Interaction, _b): await self._vote(i, "a")

    @discord.ui.button(label="B", style=discord.ButtonStyle.danger)
    async def b_btn(self, i: discord.Interaction, _b): await self._vote(i, "b")


class NumberGuessView(discord.ui.View):
    def __init__(self, target: int, user: discord.abc.User):
        super().__init__(timeout=120)
        self.target = target
        self.user = user
        self.tries = 0
        self.max_tries = 7

    @discord.ui.button(label="Tebak", style=discord.ButtonStyle.primary)
    async def guess(self, interaction: discord.Interaction, _b):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Ini bukan game kamu!", ephemeral=True)
            return
        await interaction.response.send_modal(NumberGuessModal(self))


class NumberGuessModal(discord.ui.Modal, title="Tebak angka 1-100"):
    answer = discord.ui.TextInput(label="Tebakanmu", placeholder="1-100", max_length=3)

    def __init__(self, view: NumberGuessView):
        super().__init__()
        self.view_ref = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            n = int(self.answer.value)
        except ValueError:
            await interaction.response.send_message("Harus angka.", ephemeral=True)
            return
        v = self.view_ref
        v.tries += 1
        if n == v.target:
            for c in v.children:
                if isinstance(c, discord.ui.Button):
                    c.disabled = True
            reward = max(3, 17 - 2 * v.tries)
            if interaction.guild:
                import stats as stats_mod
                await stats_mod.add_points(
                    interaction.guild.id, interaction.user.id, reward, "numberguess"
                )
            await interaction.response.send_message(
                f"🎯 **{interaction.user.display_name}** nebak bener di percobaan ke-{v.tries}! Angkanya **{v.target}**. (+{reward} poin)"
            )
            v.stop()
            return
        if v.tries >= v.max_tries:
            for c in v.children:
                if isinstance(c, discord.ui.Button):
                    c.disabled = True
            if interaction.guild:
                import stats as stats_mod
                await stats_mod.add_loss(
                    interaction.guild.id, interaction.user.id, "numberguess"
                )
            await interaction.response.send_message(
                f"💀 Game over. Angkanya **{v.target}**.", ephemeral=False
            )
            v.stop()
            return
        hint = "lebih besar" if n < v.target else "lebih kecil"
        await interaction.response.send_message(
            f"Salah! Angkanya **{hint}**. Sisa: {v.max_tries - v.tries} tebakan.", ephemeral=True
        )


class TicTacToeView(discord.ui.View):
    def __init__(self, p1: discord.abc.User, p2: discord.abc.User):
        super().__init__(timeout=300)
        self.players = [p1, p2]
        self.symbols = ["❌", "⭕"]
        self.turn = 0
        self.board = [None] * 9
        for i in range(9):
            btn = discord.ui.Button(label="\u200b", style=discord.ButtonStyle.secondary, row=i // 3)
            btn.callback = self._make_cb(i)
            self.add_item(btn)

    def _make_cb(self, idx: int):
        async def cb(interaction: discord.Interaction):
            cur = self.players[self.turn]
            if interaction.user.id != cur.id:
                await interaction.response.send_message("Bukan giliranmu!", ephemeral=True)
                return
            if self.board[idx] is not None:
                await interaction.response.send_message("Kotak sudah terisi.", ephemeral=True)
                return
            sym = self.symbols[self.turn]
            self.board[idx] = self.turn
            btn = self.children[idx]
            assert isinstance(btn, discord.ui.Button)
            btn.label = sym
            btn.disabled = True
            btn.style = discord.ButtonStyle.danger if self.turn == 0 else discord.ButtonStyle.success
            winner = self._winner()
            content = self._title()
            if winner is not None:
                for c in self.children:
                    if isinstance(c, discord.ui.Button):
                        c.disabled = True
                if winner == -1:
                    content = "🤝 Seri!"
                else:
                    win_user = self.players[winner]
                    content = f"🏆 **{win_user.display_name}** menang! +10 poin"
                    if interaction.guild:
                        import stats as stats_mod
                        await stats_mod.add_points(
                            interaction.guild.id, win_user.id, 10, "tictactoe"
                        )
                        loser = self.players[1 - winner]
                        await stats_mod.add_loss(
                            interaction.guild.id, loser.id, "tictactoe"
                        )
                self.stop()
            else:
                self.turn = 1 - self.turn
                content = self._title()
            await interaction.response.edit_message(content=content, view=self)
        return cb

    def _title(self) -> str:
        cur = self.players[self.turn]
        return f"Tic Tac Toe — Giliran {cur.mention} ({self.symbols[self.turn]})"

    def _winner(self) -> int | None:
        wins = [
            (0, 1, 2), (3, 4, 5), (6, 7, 8),
            (0, 3, 6), (1, 4, 7), (2, 5, 8),
            (0, 4, 8), (2, 4, 6),
        ]
        for a, b, c in wins:
            if self.board[a] is not None and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        if all(x is not None for x in self.board):
            return -1
        return None


class ReactionTestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.winner: discord.abc.User | None = None
        self.start_time: float | None = None

    @discord.ui.button(label="KLIK!", style=discord.ButtonStyle.success, emoji="⚡")
    async def click(self, interaction: discord.Interaction, _b):
        if self.winner is not None:
            await interaction.response.send_message("Udah ada yang menang.", ephemeral=True)
            return
        if self.start_time is None:
            await interaction.response.send_message("Belum mulai!", ephemeral=True)
            return
        self.winner = interaction.user
        elapsed = asyncio.get_event_loop().time() - self.start_time
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        if interaction.guild:
            import stats as stats_mod
            await stats_mod.add_points(
                interaction.guild.id, interaction.user.id, 8, "reactiontest"
            )
        await interaction.response.edit_message(
            content=f"⚡ **{interaction.user.display_name}** menang! Waktu reaksi: `{elapsed:.3f}s` (+8 poin)",
            view=self,
        )
        self.stop()


class HigherLowerView(discord.ui.View):
    def __init__(self, user: discord.abc.User):
        super().__init__(timeout=120)
        self.user = user
        self.current = random.randint(2, 13)
        self.score = 0

    def _card(self, n: int) -> str:
        names = {1: "A", 11: "J", 12: "Q", 13: "K"}
        return names.get(n, str(n))

    async def _guess(self, interaction: discord.Interaction, higher: bool):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Ini bukan game kamu!", ephemeral=True)
            return
        nxt = random.randint(1, 13)
        correct = (nxt > self.current) if higher else (nxt < self.current)
        if nxt == self.current:
            await interaction.response.edit_message(
                content=f"Kartu sama (**{self._card(nxt)}**). Lanjut. Skor: **{self.score}**",
                view=self,
            )
            self.current = nxt
            return
        if correct:
            self.score += 1
            self.current = nxt
            await interaction.response.edit_message(
                content=f"✅ Kartu: **{self._card(nxt)}**. Skor: **{self.score}**. Lanjut?",
                view=self,
            )
        else:
            for c in self.children:
                if isinstance(c, discord.ui.Button):
                    c.disabled = True
            reward = self.score
            extra = ""
            if reward > 0 and interaction.guild:
                import stats as stats_mod
                await stats_mod.add_points(
                    interaction.guild.id, interaction.user.id, reward, "higherlower"
                )
                extra = f" (+{reward} poin)"
            elif interaction.guild:
                import stats as stats_mod
                await stats_mod.add_loss(
                    interaction.guild.id, interaction.user.id, "higherlower"
                )
            await interaction.response.edit_message(
                content=f"❌ Kartu: **{self._card(nxt)}**. Game over! Skor akhir: **{self.score}**{extra}",
                view=self,
            )
            self.stop()

    @discord.ui.button(label="Higher", style=discord.ButtonStyle.success, emoji="⬆️")
    async def higher(self, i: discord.Interaction, _b): await self._guess(i, True)

    @discord.ui.button(label="Lower", style=discord.ButtonStyle.danger, emoji="⬇️")
    async def lower(self, i: discord.Interaction, _b): await self._guess(i, False)


class Games(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="trivia", description="Mainin trivia (English) dengan tombol pilihan.")
    async def trivia(self, interaction: discord.Interaction):
        await interaction.response.defer()
        q = await asyncio.to_thread(fetch_trivia)
        if not q:
            await interaction.followup.send("Gagal ambil pertanyaan trivia.")
            return
        choices = q["incorrect"] + [q["correct"]]
        random.shuffle(choices)
        view = TriviaView(q["correct"], choices, interaction.user)
        embed = discord.Embed(
            title=f"Trivia — {q['category']} ({q['difficulty']})",
            description=q["question"],
            color=discord.Color.gold(),
        )
        embed.set_footer(text="30 detik untuk jawab")
        await interaction.followup.send(embed=embed, view=view)
        await view.wait()
        if view.winners:
            await interaction.followup.send(f"🏆 Yang bener: {', '.join(view.winners)}")
        else:
            await interaction.followup.send(f"Waktu habis. Jawaban: **{q['correct']}**")

    @app_commands.command(name="8ball", description="Tanya magic 8-ball.")
    @app_commands.describe(question="Pertanyaan kamu")
    async def eightball(self, interaction: discord.Interaction, question: str):
        embed = discord.Embed(title="🎱 Magic 8-Ball", color=discord.Color.dark_blue())
        embed.add_field(name="Pertanyaan", value=question, inline=False)
        embed.add_field(name="Jawaban", value=random.choice(EIGHTBALL), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rps", description="Rock Paper Scissors lawan bot.")
    async def rps(self, interaction: discord.Interaction):
        view = RPSView(interaction.user)
        await interaction.response.send_message("Pilih: 🪨 / 📄 / ✂️", view=view)

    @app_commands.command(name="numberguess", description="Tebak angka 1-100 (7 percobaan).")
    async def numberguess(self, interaction: discord.Interaction):
        target = random.randint(1, 100)
        view = NumberGuessView(target, interaction.user)
        await interaction.response.send_message(
            f"Aku mikirin angka 1-100. Klik **Tebak** untuk coba. Sisa: 7 percobaan.",
            view=view,
        )

    @app_commands.command(name="wouldyourather", description="Would You Rather dengan voting.")
    async def wyr(self, interaction: discord.Interaction):
        a, b = random.choice(WYR)
        embed = discord.Embed(title="Would You Rather?", color=discord.Color.purple())
        embed.add_field(name="A", value=a, inline=False)
        embed.add_field(name="B", value=b, inline=False)
        view = WYRView(a, b)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="neverhaveiever", description="Pernyataan Never Have I Ever random.")
    async def nhie(self, interaction: discord.Interaction):
        s = random.choice(NHIE)
        embed = discord.Embed(
            title="Never Have I Ever",
            description=f"Aku belum pernah {s}",
            color=discord.Color.teal(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="thisorthat", description="Pilih: ini atau itu?")
    async def thisorthat(self, interaction: discord.Interaction):
        a, b = random.choice(THIS_OR_THAT)
        embed = discord.Embed(title="This or That?", color=discord.Color.orange())
        embed.add_field(name="A", value=a, inline=True)
        embed.add_field(name="B", value=b, inline=True)
        view = WYRView(a, b)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="slots", description="Slot machine!")
    async def slots(self, interaction: discord.Interaction):
        symbols = ["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"]
        roll = [random.choice(symbols) for _ in range(3)]
        line = " | ".join(roll)
        if roll[0] == roll[1] == roll[2]:
            result = "🎉 JACKPOT! Semua sama!"
        elif len(set(roll)) == 2:
            result = "✨ Dua sama, lumayan."
        else:
            result = "💀 Coba lagi."
        embed = discord.Embed(title="🎰 Slot Machine", description=f"```\n{line}\n```\n{result}", color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="tictactoe", description="Tic Tac Toe 1v1.")
    @app_commands.describe(opponent="Lawan kamu")
    async def tictactoe(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot:
            await interaction.response.send_message("Nggak bisa lawan bot.", ephemeral=True)
            return
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("Nggak bisa lawan diri sendiri.", ephemeral=True)
            return
        view = TicTacToeView(interaction.user, opponent)
        await interaction.response.send_message(view._title(), view=view)

    @app_commands.command(name="reactiontest", description="Tes kecepatan reaksi — siapa cepat dia menang.")
    async def reactiontest(self, interaction: discord.Interaction):
        view = ReactionTestView()
        for c in view.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        await interaction.response.send_message("Siap-siap... tunggu tombol aktif!", view=view)
        msg = await interaction.original_response()
        delay = random.uniform(2.0, 6.0)
        await asyncio.sleep(delay)
        for c in view.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = False
        view.start_time = asyncio.get_event_loop().time()
        await msg.edit(content="⚡ KLIK SEKARANG!", view=view)

    @app_commands.command(name="scramble", description="Tebak kata yang diacak — ketik jawaban di chat.")
    async def scramble(self, interaction: discord.Interaction):
        word = random.choice(SCRAMBLE_WORDS)
        scrambled = shuffle_word(word)
        await interaction.response.send_message(
            f"Tebak kata ini (30s): **`{scrambled}`**"
        )

        def check(m: discord.Message) -> bool:
            return (
                m.channel.id == interaction.channel_id
                and not m.author.bot
                and m.content.lower().strip() == word
            )

        try:
            msg = await self.bot.wait_for("message", timeout=30.0, check=check)
            if interaction.guild:
                import stats as stats_mod
                await stats_mod.add_points(
                    interaction.guild.id, msg.author.id, 10, "scramble"
                )
            await interaction.followup.send(f"✅ **{msg.author.display_name}** bener! Jawaban: **{word}** (+10 poin)")
        except asyncio.TimeoutError:
            await interaction.followup.send(f"⏰ Waktu habis. Jawaban: **{word}**")

    @app_commands.command(name="math", description="Soal matematika cepat — ketik jawabanmu.")
    async def math_quiz(self, interaction: discord.Interaction):
        a = random.randint(2, 50)
        b = random.randint(2, 50)
        op = random.choice(["+", "-", "*"])
        expr = f"{a} {op} {b}"
        answer = eval(expr)  # safe: only digits + ops
        await interaction.response.send_message(f"🧮 Berapa **{expr}**? (15s)")

        def check(m: discord.Message) -> bool:
            if m.channel.id != interaction.channel_id or m.author.bot:
                return False
            try:
                return int(m.content.strip()) == answer
            except ValueError:
                return False

        try:
            msg = await self.bot.wait_for("message", timeout=15.0, check=check)
            if interaction.guild:
                import stats as stats_mod
                await stats_mod.add_points(
                    interaction.guild.id, msg.author.id, 5, "math"
                )
            await interaction.followup.send(f"✅ **{msg.author.display_name}** bener! = **{answer}** (+5 poin)")
        except asyncio.TimeoutError:
            await interaction.followup.send(f"⏰ Waktu habis. = **{answer}**")

    @app_commands.command(name="higherlower", description="Higher or Lower — kartu A-K.")
    async def higherlower(self, interaction: discord.Interaction):
        view = HigherLowerView(interaction.user)
        await interaction.response.send_message(
            f"Kartu sekarang: **{view._card(view.current)}**. Higher atau Lower?",
            view=view,
        )

    @app_commands.command(name="russianroulette", description="Russian Roulette — 1 dari 6 peluang.")
    async def russianroulette(self, interaction: discord.Interaction):
        if random.randint(1, 6) == 1:
            await interaction.response.send_message(
                f"💥 BANG! {interaction.user.mention} kena. Game over."
            )
        else:
            await interaction.response.send_message(
                f"😮 *click*. {interaction.user.mention} selamat... untuk sekarang."
            )

    @app_commands.command(name="dice", description="Lempar dadu (default 1d6).")
    @app_commands.describe(dice="Format NdN")
    async def dice(self, interaction: discord.Interaction, dice: str = "1d6"):
        try:
            cstr, sstr = dice.lower().split("d", 1)
            count = int(cstr) if cstr else 1
            sides = int(sstr)
            if not (1 <= count <= 100) or not (2 <= sides <= 1000):
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Format `NdN`, mis. `2d6`.", ephemeral=True)
            return
        rolls = [random.randint(1, sides) for _ in range(count)]
        await interaction.response.send_message(
            f"🎲 {interaction.user.mention} dapet **{sum(rolls)}** ({', '.join(map(str, rolls))})"
        )

    @app_commands.command(name="games", description="Daftar semua minigames.")
    async def games_list(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🎮 Minigames", color=discord.Color.fuchsia())
        cmds = [
            ("/trivia", "Pertanyaan multiple-choice (Open Trivia DB)"),
            ("/8ball", "Magic 8-ball"),
            ("/rps", "Rock Paper Scissors lawan bot"),
            ("/numberguess", "Tebak angka 1-100"),
            ("/wouldyourather", "WYR + voting"),
            ("/neverhaveiever", "Pernyataan NHIE random"),
            ("/thisorthat", "Voting: ini atau itu"),
            ("/slots", "Slot machine"),
            ("/tictactoe", "Tic Tac Toe 1v1"),
            ("/reactiontest", "Tes reaksi — siapa cepat dia menang"),
            ("/scramble", "Tebak kata acak"),
            ("/math", "Soal matematika cepat"),
            ("/higherlower", "Higher or lower (kartu)"),
            ("/russianroulette", "Russian roulette"),
            ("/dice", "Lempar dadu NdN"),
            ("/tod", "Truth or Dare (Indonesia)"),
        ]
        for name, desc in cmds:
            embed.add_field(name=name, value=desc, inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Games(bot))
    log.info("Games cog loaded.")
