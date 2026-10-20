import asyncio
import ctypes
import tempfile
from pathlib import Path

from discord.ext.commands import Context


async def set_wallpaper(ctx: Context):
    # Find an image attached to the command message.
    attachment = next(
        (
            a
            for a in ctx.message.attachments
            if a.content_type and a.content_type.startswith("image/")
        ),
        None,
    )

    if attachment is None:
        await ctx.reply(
            "Please attach an image to your message, for example: `!wallpaper`"
        )
        return

    # Save the image locally.
    suffix = Path(attachment.filename).suffix.lower()
    allowed_extensions = {".jpg", ".jpeg", ".png", ".bmp"}
    if suffix not in allowed_extensions:
        await ctx.reply("Please attach a JPG, JPEG, PNG, or BMP image.")
        return

    if attachment.size > 15 * 1024 * 1024:
        await ctx.reply("The image must be smaller than 15 MB.")
        return

    wallpaper_path = Path(tempfile.gettempdir()) / f"discord_wallpaper{suffix}"

    try:
        await attachment.save(wallpaper_path)

        # Windows API function to update the desktop wallpaper.
        SPI_SETDESKWALLPAPER = 20
        SPIF_UPDATEINIFILE = 1
        SPIF_SENDCHANGE = 2

        def set_wallpaper():
            result = ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER,
                0,
                str(wallpaper_path.resolve()),
                SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
            )
            if not result:
                raise ctypes.WinError()

        await asyncio.to_thread(set_wallpaper)

        await ctx.reply("Desktop wallpaper updated successfully.")

    except Exception as exc:
        await ctx.reply(f"Could not set wallpaper: {type(exc).__name__}: {exc}")

    finally:
        # Keep the image file: Windows may need it after the API call.
        pass
