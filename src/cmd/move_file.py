import asyncio
import shutil
from pathlib import Path

from discord.ext import commands
from discord.ext.commands import Context


async def move_file(ctx: Context[commands.Bot], paths: str) -> None:
    import shlex

    try:
        args = shlex.split(paths, posix=False)
        args = [arg.strip('"') for arg in args]

        if len(args) != 2:
            await ctx.reply('Usage: `!move "source_path" "destination_path"`')
            return

        source = Path(args[0]).expanduser()
        destination = Path(args[1]).expanduser()

        if not source.exists():
            await ctx.reply(f"Source does not exist: `{source}`")
            return

        if source.resolve() == destination.resolve():
            await ctx.reply("Source and destination are the same path.")
            return

        if destination.exists() and destination.is_dir():
            destination = destination / source.name

        await asyncio.to_thread(shutil.move, str(source), str(destination))

        await ctx.reply(f"Moved `{source}` to `{destination}` successfully.")

    except Exception as e:
        await ctx.reply(f"Move failed: {type(e).__name__}: {e}")
