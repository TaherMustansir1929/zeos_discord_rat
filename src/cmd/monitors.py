"""Switch the monitors of the host on and off."""

import asyncio

import monitorcontrol
from discord.ext import commands
from discord.ext.commands import Context

# Power modes of the Windows display API.
POWER_MODE_ON = 1
POWER_MODE_OFF = 4


def set_monitor_power(power_mode: int) -> tuple[int, int]:
    """Set the power mode of every monitor and report how many were changed.

    The first number of the result is the amount of monitors that were
    found, the second one the amount of monitors that accepted the change.
    """
    monitors = monitorcontrol.get_monitors()
    changed = 0

    for monitor in monitors:
        try:
            monitor.set_power_mode(power_mode)
            changed += 1
        except Exception as exc:
            print(f"Monitor error: {exc}")

    return len(monitors), changed


async def set_monitors(ctx: Context[commands.Bot], state: str) -> None:
    """Switch the monitors of the host on or off."""
    choice = state.strip().lower()

    if choice not in ("on", "off"):
        await ctx.reply("Usage: `!monitors <on|off>`")
        return

    power_mode = POWER_MODE_ON if choice == "on" else POWER_MODE_OFF

    try:
        found, changed = await asyncio.to_thread(set_monitor_power, power_mode)
    except Exception as exc:
        print(f"Monitor error: {exc}")
        await ctx.reply("Could not talk to the monitors of this computer.")
        return

    if not found:
        await ctx.reply("No monitor was found on this computer.")
        return

    await ctx.reply(f"Switched {changed} of {found} monitors {choice}.")
