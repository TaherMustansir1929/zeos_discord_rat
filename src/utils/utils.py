import io
from pathlib import Path

import discord
from discord.ext import commands
from discord.ext.commands import Context

from src.constants import INSTALL_DIR

# Discord's per-message character limit.
CHUNK_SIZE = 2000


def state_file(name: str) -> Path:
    """Return the path of a state file that the runtime keeps.

    The state files hold the settings that have to survive a restart, so
    they live next to the installed executable. When that folder cannot be
    used, the current working directory is used instead.
    """
    try:
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        return INSTALL_DIR / name
    except OSError:
        return Path.cwd() / name


async def send_text_in_chunks(
    ctx: Context[commands.Bot],
    text: str,
    filename: str = "output.txt",
    file_threshold: int = 10000,
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
