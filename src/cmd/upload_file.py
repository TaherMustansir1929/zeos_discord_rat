from pathlib import Path
from urllib.parse import unquote, urlparse

import aiohttp
import discord
from discord.ext.commands import Context

DOWNLOAD_DIR = Path("downloads")


async def upload_file(ctx: Context, url: str | None = None):
    """Download a file from an attachment or URL and upload it to Discord."""

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = None

    try:
        # Option 1: A file attached to the Discord message.
        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]

            filename = Path(attachment.filename).name
            file_path = DOWNLOAD_DIR / filename

            await attachment.save(file_path)

        # Option 2: A direct file URL.
        elif url:
            parsed = urlparse(url)

            if (
                parsed.scheme not in ("http", "https")
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
            ):
                await ctx.reply("Please provide a valid HTTP/HTTPS file URL.")
                return

            timeout = aiohttp.ClientTimeout(total=60)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    url,
                    allow_redirects=False,
                ) as response:
                    if response.status != 200:
                        await ctx.reply(f"Download failed (HTTP {response.status}).")
                        return

                    filename = Path(unquote(parsed.path)).name or "download.bin"

                    filename = Path(filename).name
                    file_path = DOWNLOAD_DIR / filename

                    size = 0
                    with open(file_path, "wb") as output:
                        async for chunk in response.content.iter_chunked(65536):
                            size += len(chunk)
                            output.write(chunk)

        else:
            await ctx.reply(
                "Attach a file to your message or provide a direct file URL."
            )
            return

        # Upload the downloaded file to the channel.
        await ctx.send(
            content="Here is the file:",
            file=discord.File(str(file_path)),
        )

    except ValueError as exc:
        await ctx.reply(str(exc))

    except Exception as exc:
        print(f"Upload error: {exc}")
        await ctx.reply("Could not download or upload the file.")
