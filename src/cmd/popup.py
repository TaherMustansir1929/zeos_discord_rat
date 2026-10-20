import subprocess

from discord.ext.commands import Context


async def popup_show(ctx: Context, message: str):
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

    try:
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-STA", "-Command", powershell_script]
        )

        await ctx.reply("Windows pop-up launched.")

    except Exception as exc:
        await ctx.reply(f"Failed to launch pop-up: {exc}")
