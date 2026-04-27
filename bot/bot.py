import os
import random
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("bot")

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN environment variable is not set.")

COMMAND_PREFIX = os.environ.get("DISCORD_COMMAND_PREFIX", "!")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)


TRUTHS = [
    "What's the most embarrassing thing you've done in the last year?",
    "What's a secret you've never told anyone in this server?",
    "Who in this server would you trust with your phone for a day?",
    "What's the weirdest dream you've had recently?",
    "What's the worst lie you've ever told a parent?",
    "What's something you pretend to like just to fit in?",
    "What's the last thing you searched on your phone?",
    "What's the most childish thing you still do?",
    "What's a talent you wish you had?",
    "Have you ever cheated on a test? What happened?",
    "What's your biggest irrational fear?",
    "What's the worst gift you've ever received?",
    "What's something you've done that you'd never tell your parents?",
    "Who was your first crush?",
    "What's the most trouble you've ever been in?",
    "What's a habit you have that you're embarrassed about?",
    "What's your most controversial opinion about food?",
    "If you had to delete one app from your phone forever, what would it be?",
    "What's the last text you sent and to whom?",
    "What's the longest you've gone without showering?",
]

DARES = [
    "Send the 5th photo in your camera roll to this channel.",
    "Speak in a British accent for the next 3 messages.",
    "DM someone in this server a compliment right now.",
    "Type your next message with your eyes closed — no edits.",
    "Change your nickname to something the next person picks for 10 minutes.",
    "Post the most recent meme you saved.",
    "Send a voice message of you singing the chorus of any song.",
    "Tell a joke. If nobody reacts, do another dare.",
    "Type out the alphabet using only emojis.",
    "Set your status to 'I lost a dare' for 1 hour.",
    "Share an embarrassing childhood photo (or describe one in detail).",
    "Do 10 push-ups and post a video or proof.",
    "Send a screenshot of your home screen.",
    "Talk like a pirate for the next 5 minutes.",
    "Read your last sent message in a dramatic voice (post a voice clip).",
    "Replace your profile picture with a cartoon character for 24 hours.",
    "Write a 2-line poem about the person above you in chat.",
    "Send the last song you listened to.",
    "Spell your name backwards and use it as your nickname for 10 minutes.",
    "Post a selfie making the silliest face you can.",
]


class TruthOrDareView(discord.ui.View):
    def __init__(self, requester: discord.abc.User):
        super().__init__(timeout=180)
        self.requester = requester
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
        embed.set_footer(text=f"For {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, view=TruthOrDareView(interaction.user))

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
    activity = discord.Game(name=f"Lunethra.gg | {COMMAND_PREFIX}help")
    await bot.change_presence(status=discord.Status.online, activity=activity)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument: `{error.param.name}`. See `{COMMAND_PREFIX}help`.")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"Invalid argument: {error}")
        return
    log.exception("Unhandled command error", exc_info=error)
    await ctx.send("Something went wrong running that command.")


@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    p = COMMAND_PREFIX
    embed = discord.Embed(
        title="Bot Commands",
        description=f"Prefix all commands with `{p}`",
        color=discord.Color.blurple(),
    )
    embed.add_field(name=f"{p}ping", value="Show bot latency.", inline=False)
    embed.add_field(name=f"{p}hello", value="Friendly greeting.", inline=False)
    embed.add_field(name=f"{p}say <text>", value="Repeat your message.", inline=False)
    embed.add_field(name=f"{p}roll [NdN]", value="Roll dice (e.g. `2d6`). Defaults to `1d6`.", inline=False)
    embed.add_field(name=f"{p}flip", value="Flip a coin.", inline=False)
    embed.add_field(name=f"{p}choose <a> <b> ...", value="Pick one option at random.", inline=False)
    embed.add_field(name=f"{p}avatar [@user]", value="Show a user's avatar.", inline=False)
    embed.add_field(name=f"{p}userinfo [@user]", value="Show info about a user.", inline=False)
    embed.add_field(name=f"{p}serverinfo", value="Show info about this server.", inline=False)
    embed.add_field(name=f"{p}clear <n>", value="Delete the last n messages (manage messages).", inline=False)
    embed.add_field(name=f"{p}tod", value="Start a Truth or Dare game with buttons.", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="tod", aliases=["truthordare"])
async def tod(ctx: commands.Context):
    embed = discord.Embed(
        title="Truth or Dare",
        description="Pick your poison. Click a button below.",
        color=discord.Color.purple(),
    )
    embed.add_field(name="Truth", value="Answer an honest question.", inline=True)
    embed.add_field(name="Dare", value="Complete a challenge.", inline=True)
    embed.add_field(name="Random", value="Let fate decide.", inline=True)
    embed.set_footer(text=f"Started by {ctx.author.display_name}")
    view = TruthOrDareView(ctx.author)
    view.message = await ctx.send(embed=embed, view=view)


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f"Pong! `{latency_ms}ms`")


@bot.command(name="hello")
async def hello(ctx: commands.Context):
    await ctx.send(f"Hi {ctx.author.mention}!")


@bot.command(name="say")
async def say(ctx: commands.Context, *, text: str):
    await ctx.send(text)


@bot.command(name="roll")
async def roll(ctx: commands.Context, dice: str = "1d6"):
    try:
        count_str, sides_str = dice.lower().split("d", 1)
        count = int(count_str) if count_str else 1
        sides = int(sides_str)
        if not (1 <= count <= 100) or not (2 <= sides <= 1000):
            raise ValueError
    except ValueError:
        await ctx.send("Use the format `NdN`, e.g. `2d6`. Limits: 1–100 dice, 2–1000 sides.")
        return
    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls)
    detail = ", ".join(str(r) for r in rolls)
    await ctx.send(f"{ctx.author.mention} rolled **{total}** ({detail})")


@bot.command(name="flip")
async def flip(ctx: commands.Context):
    await ctx.send(random.choice(["Heads", "Tails"]))


@bot.command(name="choose")
async def choose(ctx: commands.Context, *choices: str):
    if len(choices) < 2:
        await ctx.send("Give me at least two options to choose from.")
        return
    await ctx.send(f"I pick: **{random.choice(choices)}**")


@bot.command(name="avatar")
async def avatar(ctx: commands.Context, member: discord.Member | None = None):
    target = member or ctx.author
    embed = discord.Embed(title=f"{target.display_name}'s avatar", color=discord.Color.blurple())
    embed.set_image(url=target.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="userinfo")
async def userinfo(ctx: commands.Context, member: discord.Member | None = None):
    target = member or ctx.author
    embed = discord.Embed(title=str(target), color=discord.Color.green())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="ID", value=str(target.id), inline=False)
    embed.add_field(name="Created", value=target.created_at.strftime("%Y-%m-%d %H:%M UTC"), inline=False)
    if target.joined_at:
        embed.add_field(name="Joined", value=target.joined_at.strftime("%Y-%m-%d %H:%M UTC"), inline=False)
    roles = [r.mention for r in target.roles if r.name != "@everyone"]
    if roles:
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles), inline=False)
    await ctx.send(embed=embed)


@bot.command(name="serverinfo")
@commands.guild_only()
async def serverinfo(ctx: commands.Context):
    g = ctx.guild
    assert g is not None
    embed = discord.Embed(title=g.name, color=discord.Color.gold())
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.add_field(name="ID", value=str(g.id), inline=False)
    embed.add_field(name="Owner", value=str(g.owner), inline=False)
    embed.add_field(name="Members", value=str(g.member_count), inline=True)
    embed.add_field(name="Channels", value=str(len(g.channels)), inline=True)
    embed.add_field(name="Roles", value=str(len(g.roles)), inline=True)
    embed.add_field(name="Created", value=g.created_at.strftime("%Y-%m-%d"), inline=False)
    await ctx.send(embed=embed)


@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
async def clear(ctx: commands.Context, amount: int):
    if not isinstance(ctx.channel, (discord.TextChannel, discord.Thread)):
        await ctx.send("Can only clear in text channels.")
        return
    if not (1 <= amount <= 100):
        await ctx.send("Pick a number between 1 and 100.")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    confirm = await ctx.send(f"Deleted {len(deleted) - 1} message(s).")
    await confirm.delete(delay=3)


if __name__ == "__main__":
    bot.run(TOKEN, log_handler=None)
