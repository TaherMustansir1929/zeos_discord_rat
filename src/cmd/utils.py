import io

import discord
from discord.ext import commands
from discord.ext.commands import Context

# Discord's per-message character limit.
CHUNK_SIZE = 2000
# Texts longer than this are uploaded as a file instead of being split into chunks.
FILE_THRESHOLD = 5000


async def send_text_in_chunks(
    ctx: Context[commands.Bot], text: str, filename: str = "output.txt"
) -> None:
    if not text:
        await ctx.send("(no output)")
        return

    if len(text) > FILE_THRESHOLD:
        buffer = io.BytesIO(text.encode("utf-8"))
        await ctx.send(file=discord.File(buffer, filename=filename))
        return

    for start in range(0, len(text), CHUNK_SIZE):
        await ctx.send(text[start : start + CHUNK_SIZE])
