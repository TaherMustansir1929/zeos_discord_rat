import os
import shutil
from pathlib import Path

from discord import Message
from discord.ext import commands
from discord.ext.commands import Context

CONFIRMATION_TIMEOUT = 30  # seconds


async def delete_file(
    bot: commands.Bot, ctx: Context[commands.Bot], path: str
) -> None:
    path = os.path.expandvars(os.path.expanduser(path.strip().strip('"')))

    target = Path(path)

    # Resolve relative paths from the bot's working directory.
    if not target.is_absolute():
        target = Path.cwd() / target

    target = target.resolve()

    if not target.exists():
        await ctx.reply("File or folder not found. Please check the path.")
        return

    if target.is_file():
        item_type = "file"
    elif target.is_dir():
        item_type = "folder"
    else:
        await ctx.reply("This path is not a regular file or folder.")
        return

    # Ask for explicit confirmation.
    message = await ctx.reply(
        f"⚠️ **Confirm deletion**\n"
        f"Type: `{item_type}`\n"
        f"Path: `{target}`\n\n"
        f"This action is permanent. "
        f"Reply `yes` to confirm or `no` to cancel. "
        f"You have {CONFIRMATION_TIMEOUT} seconds."
    )

    def check(m: Message) -> bool:
        return (
            m.author.id == ctx.author.id
            and m.channel.id == ctx.channel.id
            and m.content.lower().strip() in ("yes", "no")
        )

    try:
        response: Message = await bot.wait_for(
            "message", check=check, timeout=CONFIRMATION_TIMEOUT
        )
    except TimeoutError:
        await ctx.reply("Deletion cancelled: confirmation timed out.")
        return

    if response.content.lower().strip() != "yes":
        await ctx.reply("Deletion cancelled.")
        return

    try:
        # Check again in case the target changed while waiting.
        if not target.exists():
            await ctx.reply("The target no longer exists.")
            return

        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

        await ctx.reply(f"Deleted the {item_type}: `{target}`")

    except PermissionError:
        await ctx.reply("Permission denied. I cannot delete this path.")
    except OSError as exc:
        await ctx.reply(f"Deletion failed: {exc}")
