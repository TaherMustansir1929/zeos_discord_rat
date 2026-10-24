"""Commands that act on the runtime itself and on the Discord channel."""

import asyncio
import os
import subprocess
from pathlib import Path

import discord
from discord.ext import commands
from discord.ext.commands import Context

from src.constants import ASSET_NAME, INSTALL_DIR


async def clear_channel(ctx: Context[commands.Bot]) -> None:
    """Delete the messages that the runtime wrote in this channel."""
    channel = ctx.channel
    deleted = 0

    async for message in channel.history(limit=None):
        # Only the messages of the runtime are removed, the messages of
        # the owner stay untouched.
        if message.author.id != ctx.bot.user.id:
            continue

        try:
            await message.delete()
            deleted += 1
        except discord.HTTPException as exc:
            print(f"Could not delete a message: {exc}")

    await ctx.reply(f"Deleted {deleted} message(s) in this channel.")


async def restart_bot(ctx: Context[commands.Bot]) -> None:
    """Start the runtime again and stop the running process."""
    executable = Path(INSTALL_DIR) / ASSET_NAME

    if not executable.is_file():
        await ctx.reply(
            f"The runtime was not found at `{executable}`, "
            "only a packaged runtime can restart itself."
        )
        return

    try:
        subprocess.Popen(
            [str(executable)],
            cwd=str(INSTALL_DIR),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )
    except OSError as exc:
        await ctx.reply(f"Could not start the runtime again: {exc}")
        return

    await ctx.reply("The runtime restarts in a moment.")

    # The new process takes over, this one only waits for it.
    await asyncio.sleep(1)
    os._exit(0)
