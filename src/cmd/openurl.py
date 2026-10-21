import asyncio
import webbrowser
from urllib.parse import urlparse

from discord.ext import commands
from discord.ext.commands import Context


async def spawn_proc(ctx: Context[commands.Bot], url: str) -> None:
    url = url.strip()

    # Add HTTPS automatically if no scheme is provided.
    if "://" not in url:
        url = "https://" + url

    try:
        parsed = urlparse(url)

        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or any(c.isspace() for c in url)
            or "." not in parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            await ctx.reply("Please provide a valid website URL.")
            return

    except ValueError:
        await ctx.reply("Invalid URL.")
        return

    try:
        opened = await asyncio.to_thread(
            webbrowser.open,
            url,
            new=2,
        )

        if opened:
            await ctx.reply(f"Opened: {url}")
        else:
            await ctx.reply("Could not open the URL.")

    except Exception as exc:
        print(f"Browser error: {exc}")
        await ctx.reply("An error occurred while opening the URL.")
