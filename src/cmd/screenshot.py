from io import BytesIO

import discord
import pyautogui
from discord.ext.commands import Context


async def take_screenshot(ctx: Context):
    """Capture the bot host's screen and upload it to this channel."""

    try:
        # Capture the screen into memory.
        image_buffer = BytesIO()
        pyautogui.screenshot().save(image_buffer, format="PNG")
        image_buffer.seek(0)

        # Upload the image to the channel where the command was used.
        screenshot_file = discord.File(
            image_buffer,
            filename="screenshot.png",
        )

        await ctx.send(
            "Screenshot from the computer running the bot:",
            file=screenshot_file,
        )

    except Exception as e:
        await ctx.reply(
            "Screenshot failed. Check the computer's screen permissions "
            "and the bot's ability to upload files."
        )
        print(e)
