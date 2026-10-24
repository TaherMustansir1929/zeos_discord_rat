import os
from pathlib import Path

from discord.ext import commands
from discord.ext.commands import Context

from src.utils.utils import send_text_in_chunks

# Largest file that is read into memory and sent as text.
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def resolve_path(path: str) -> Path:
    """Turn a user supplied path into an absolute path.

    Environment variables and `~` are expanded, relative paths are resolved
    from the bot's working directory.
    """
    cleaned = os.path.expandvars(os.path.expanduser(path.strip().strip('"')))
    target = Path(cleaned)

    if not target.is_absolute():
        target = Path.cwd() / target

    return target.resolve()


async def read_file(ctx: Context[commands.Bot], path: str) -> None:
    """Read a file from disk and send its contents as text."""
    target = resolve_path(path)

    if not target.exists():
        await ctx.reply(f"File not found: `{target}`")
        return

    if not target.is_file():
        await ctx.reply(f"Not a file: `{target}`")
        return

    try:
        size = target.stat().st_size

        if size > MAX_FILE_SIZE:
            await ctx.reply(
                f"File is too large to read ({size} bytes). "
                f"Use `!download` to fetch it instead."
            )
            return

        data = target.read_bytes()
    except OSError as exc:
        await ctx.reply(f"Could not read the file: {exc}")
        return

    # Binary content is not readable as text.
    if b"\x00" in data[:4096]:
        await ctx.reply(
            "This looks like a binary file. Use `!download` to fetch it instead."
        )
        return

    text = data.decode("utf-8", errors="replace")

    await send_text_in_chunks(ctx, text, filename=target.name)
