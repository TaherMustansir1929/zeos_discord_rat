"""Send key presses and shortcuts to the machine that runs the bot.

The shortcuts are recognised by their name, so `alttab` switches the
window and `ctrlc` copies the selection. Everything that is not a known
shortcut is typed character by character.
"""

import asyncio

import pyautogui
from discord.ext import commands
from discord.ext.commands import Context

# The shortcuts that are sent as a combination of keys.
HOTKEYS: dict[str, tuple[str, ...]] = {
    "altf4": ("alt", "f4"),
    "alttab": ("alt", "tab"),
    "ctrlc": ("ctrl", "c"),
    "ctrlv": ("ctrl", "v"),
}

# The single keys that are sent with a plain press.
PRESSES: dict[str, str] = {
    "enter": "enter",
    "escape": "esc",
    "esc": "esc",
}


async def press_keys(ctx: Context[commands.Bot], keys: str) -> None:
    """Send the given keys or shortcut to this machine."""
    text = keys.strip()

    if not text:
        await ctx.reply("Give the keys to press, for example `!keys alttab`.")
        return

    # The names of the shortcuts are case insensitive and may be written
    # with spaces in between.
    name = text.lower().replace(" ", "")

    try:
        if name in HOTKEYS:
            await asyncio.to_thread(pyautogui.hotkey, *HOTKEYS[name])
            await ctx.reply(f"Pressed {name}.")
            return

        if name in PRESSES:
            await asyncio.to_thread(pyautogui.press, PRESSES[name])
            await ctx.reply(f"Pressed {name}.")
            return

        await asyncio.to_thread(pyautogui.typewrite, text)
        await ctx.reply(f"Typed {text}.")

    except Exception as exc:
        print(f"[-] Could not send the keys: {exc}")
        await ctx.reply("Could not send the keys.")
