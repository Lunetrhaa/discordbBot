import asyncio
import base64
import io
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from openai import AsyncOpenAI

log = logging.getLogger("bot.ai")

SIZE_CHOICES = [
    app_commands.Choice(name="Square (1024x1024)", value="1024x1024"),
    app_commands.Choice(name="Landscape (1536x1024)", value="1536x1024"),
    app_commands.Choice(name="Portrait (1024x1536)", value="1024x1536"),
]

QUALITY_CHOICES = [
    app_commands.Choice(name="Low (cepat)", value="low"),
    app_commands.Choice(name="Medium", value="medium"),
    app_commands.Choice(name="High (detail)", value="high"),
]


class AICog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
        if not base_url or not api_key:
            log.warning("OpenAI integration env vars missing — /imagine will fail")
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key or "missing")

    async def _generate(self, prompt: str, size: str, quality: str) -> bytes:
        result = await self.client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
        )
        b64 = result.data[0].b64_json
        if not b64:
            raise RuntimeError("No image returned")
        return base64.b64decode(b64)

    @app_commands.command(name="imagine", description="Bikin gambar dari prompt teks pakai AI.")
    @app_commands.describe(
        prompt="Deskripsi gambar yang mau dibikin",
        size="Ukuran gambar (default square)",
        quality="Kualitas gambar (default medium)",
    )
    @app_commands.choices(size=SIZE_CHOICES, quality=QUALITY_CHOICES)
    async def imagine(
        self,
        interaction: discord.Interaction,
        prompt: str,
        size: app_commands.Choice[str] | None = None,
        quality: app_commands.Choice[str] | None = None,
    ):
        size_val = size.value if size else "1024x1024"
        quality_val = quality.value if quality else "medium"
        if len(prompt) > 1000:
            await interaction.response.send_message("Prompt maks 1000 karakter.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        try:
            data = await asyncio.wait_for(
                self._generate(prompt, size_val, quality_val), timeout=120
            )
        except asyncio.TimeoutError:
            await interaction.followup.send("Timeout saat bikin gambar. Coba lagi.")
            return
        except Exception as e:
            log.exception("Image generation failed")
            await interaction.followup.send(f"Gagal bikin gambar: `{e}`")
            return
        file = discord.File(io.BytesIO(data), filename="imagine.png")
        embed = discord.Embed(
            title="🎨 Generated",
            description=f"**Prompt:** {prompt[:1000]}",
            color=discord.Color.fuchsia(),
        )
        embed.add_field(name="Ukuran", value=size_val, inline=True)
        embed.add_field(name="Kualitas", value=quality_val, inline=True)
        embed.add_field(name="Diminta oleh", value=interaction.user.mention, inline=True)
        embed.set_image(url="attachment://imagine.png")
        await interaction.followup.send(embed=embed, file=file)


async def setup(bot: commands.Bot):
    await bot.add_cog(AICog(bot))
    log.info("AI cog loaded.")
