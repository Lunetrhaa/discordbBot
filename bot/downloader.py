import asyncio
import logging
import re
import tempfile
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from . import yt_dlp

log = logging.getLogger("bot.downloader")

URL_RE = re.compile(r"https?://\S+")
# Discord upload limit for non-boosted servers is 25 MB (10 MB historically). Keep margin.
MAX_BYTES = 24 * 1024 * 1024


def _parse_url(text: str) -> str | None:
    m = URL_RE.search(text)
    return m.group(0) if m else None


async def _download(url: str, audio_only: bool, tmpdir: str) -> tuple[Path, dict]:
    out_tpl = str(Path(tmpdir) / "dl.%(ext)s")
    if audio_only:
        opts = {
            "format": "bestaudio/best",
            "outtmpl": out_tpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "max_filesize": MAX_BYTES,
        }
    else:
        opts = {
            "format": f"best[filesize<{MAX_BYTES}]/best[filesize_approx<{MAX_BYTES}]/worst",
            "outtmpl": out_tpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
            "max_filesize": MAX_BYTES,
        }

    def _do():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info

    info = await asyncio.to_thread(_do)
    files = sorted(Path(tmpdir).glob("dl.*"), key=lambda p: -p.stat().st_size)
    if not files:
        raise RuntimeError("Tidak ada file ter-download.")
    return files[0], info


async def _do_download(
    interaction: discord.Interaction, raw_url: str, audio_only: bool, label: str
):
    url = _parse_url(raw_url)
    if not url:
        await interaction.response.send_message("URL tidak valid.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                file_path, info = await asyncio.wait_for(
                    _download(url, audio_only, tmpdir), timeout=120
                )
            except asyncio.TimeoutError:
                await interaction.followup.send("⏱️ Timeout (120s). Video terlalu besar/lambat.")
                return
            size = file_path.stat().st_size
            if size > MAX_BYTES:
                await interaction.followup.send(
                    f"⚠️ File ({size // 1024 // 1024} MB) lebih besar dari batas Discord ({MAX_BYTES // 1024 // 1024} MB)."
                )
                return
            title = (info.get("title") or "media")[:60]
            ext = "mp3" if audio_only else "mp4"
            filename = f"{re.sub(r'[^A-Za-z0-9_-]+', '_', title)}.{ext}"
            embed = discord.Embed(
                title=f"📥 {label}",
                description=f"**{title}**",
                color=discord.Color.from_str("#FF0050") if label == "TikTok" else discord.Color.red(),
            )
            uploader = info.get("uploader") or info.get("uploader_id") or "?"
            embed.add_field(name="Uploader", value=str(uploader), inline=True)
            duration = info.get("duration")
            if duration:
                embed.add_field(name="Durasi", value=f"{int(duration)}s", inline=True)
            embed.add_field(name="Diminta oleh", value=interaction.user.mention, inline=True)
            try:
                await interaction.followup.send(
                    embed=embed,
                    file=discord.File(str(file_path), filename=filename),
                )
            except discord.HTTPException as e:
                await interaction.followup.send(f"Gagal upload ke Discord: `{e}`")
    except yt_dlp.utils.DownloadError as e:
        await interaction.followup.send(f"❌ Download gagal: `{str(e)[:300]}`")
    except Exception as e:
        log.exception("Download failure")
        await interaction.followup.send(f"❌ Error: `{e}`")


class DownloaderCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="vt", description="Download video TikTok jadi MP4.")
    @app_commands.describe(url="Link TikTok", audio="Set true buat ambil audio MP3 saja")
    async def vt(self, interaction: discord.Interaction, url: str, audio: bool = False):
        await _do_download(interaction, url, audio, "TikTok")

    @app_commands.command(name="yt", description="Download video YouTube jadi MP4 atau MP3.")
    @app_commands.describe(url="Link YouTube", audio="Set true buat ambil audio MP3 saja")
    async def yt(self, interaction: discord.Interaction, url: str, audio: bool = False):
        await _do_download(interaction, url, audio, "YouTube")

    @app_commands.command(name="dl", description="Download video apapun (Twitter/IG/Reddit/dll) jadi MP4 atau MP3.")
    @app_commands.describe(url="Link video", audio="Set true buat ambil audio MP3 saja")
    async def dl(self, interaction: discord.Interaction, url: str, audio: bool = False):
        await _do_download(interaction, url, audio, "Media")


async def setup(bot: commands.Bot):
    await bot.add_cog(DownloaderCog(bot))
    log.info("Downloader cog loaded.")
