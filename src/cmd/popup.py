import asyncio
import base64

from discord.ext import commands
from discord.ext.commands import Context

from src.cmd.shell import execute_cmd


async def popup_show(ctx: Context[commands.Bot], message: str) -> None:
    """Show a Windows message box on the host."""
    # Escape single quotes for PowerShell.
    safe_message = message.replace("'", "''")

    powershell_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.MessageBox]::Show("
        f"'{safe_message}', "
        "'Network', "
        "[System.Windows.Forms.MessageBoxButtons]::OK, "
        "[System.Windows.Forms.MessageBoxIcon]::Information)"
    )

    # The script is base64 encoded so it reaches the child process unchanged,
    # whatever characters the message contains.
    encoded = base64.b64encode(powershell_script.encode("utf-16-le")).decode("ascii")

    try:
        # The pop-up runs in its own hidden process, so the shared session
        # stays free while the message box is open.
        await asyncio.to_thread(
            execute_cmd,
            "Start-Process powershell.exe -WindowStyle Hidden "
            f"-ArgumentList '-NoProfile','-STA','-EncodedCommand','{encoded}'",
        )

        await ctx.reply("Windows pop-up launched.")

    except Exception as exc:
        await ctx.reply(f"Failed to launch pop-up: {exc}")
