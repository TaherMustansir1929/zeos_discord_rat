import io

import discord
from discord.ext import commands
from discord.ext.commands import Context

# Discord's per-message character limit.
CHUNK_SIZE = 2000


async def send_text_in_chunks(
    ctx: Context[commands.Bot],
    text: str,
    filename: str = "output.txt",
    file_threshold: int = 5000,
) -> None:
    """Send text to Discord, picking the delivery method based on its length.

    Texts longer than `file_threshold` characters are uploaded as a text file,
    shorter ones are split into messages of at most CHUNK_SIZE characters.
    """
    if not text:
        await ctx.send("(no output)")
        return

    if len(text) > file_threshold:
        buffer = io.BytesIO(text.encode("utf-8"))
        await ctx.send(file=discord.File(buffer, filename=filename))
        return

    for start in range(0, len(text), CHUNK_SIZE):
        await ctx.send(text[start : start + CHUNK_SIZE])
