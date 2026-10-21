import os
from pathlib import Path

import discord
from discord.ext import commands
from discord.ext.commands import Context


async def download_file(ctx: Context[commands.Bot], path: str) -> None:
    """Resolve a file path and send the file to Discord."""

    path = os.path.expandvars(os.path.expanduser(path.strip().strip('"')))

    file_path = Path(path)

    # Relative paths are resolved from the bot's working directory.
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path

    if not file_path.is_file():
        await ctx.reply("File not found. Please check the file path.")
        return

    with file_path.open("rb") as file:
        await ctx.send(
            content=f"File: {file_path.name}",
            file=discord.File(file, filename=file_path.name),
        )
