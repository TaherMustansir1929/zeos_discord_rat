import asyncio
import io

import discord
import pyperclip
from discord.ext import commands
from discord.ext.commands import Context


async def get_clipboard(
    ctx: Context[commands.Bot], action: str = "read", text: str | None = None
) -> None:
    try:
        if action.lower() == "read":
            content: str = await asyncio.to_thread(pyperclip.paste)

            if not content:
                await ctx.reply("The clipboard is empty or contains no text.")
                return

            # Send long text as a file to avoid Discord's message limit.
            if len(content) > 1900:
                file = discord.File(
                    io.BytesIO(content.encode("utf-8")), filename="clipboard.txt"
                )
                await ctx.send(file=file)
            else:
                await ctx.send(f"```text\n{content}\n```")

        elif action.lower() == "write":
            if not text:
                await ctx.reply("Usage: `!clipboard write your text here`")
                return

            await asyncio.to_thread(pyperclip.copy, text)
            await ctx.reply("Clipboard text updated.")

        else:
            await ctx.reply("Use `!clipboard read` or `!clipboard write your text`.")

    except Exception as e:
        await ctx.reply(f"Clipboard error: {type(e).__name__}: {e}")
