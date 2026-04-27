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


@bot.event
async def on_ready():
    log.info("Logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "?")
    log.info("Connected to %d guild(s).", len(bot.guilds))
    activity = discord.Game(name=f"{COMMAND_PREFIX}help")
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
    await ctx.send(embed=embed)


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
