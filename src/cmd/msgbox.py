import asyncio
import json
import os
import re
import subprocess

from discord.ext import commands
from discord.ext.commands import Context


async def msgbox_show(ctx: Context[commands.Bot], args: str) -> None:
    # Extract the quoted prompt from the end of the input.
    match = re.search(r'"([^"]*)"\s*$', args)

    if not match:
        await ctx.reply('Usage: `!msgbox option1, option2, option3 "Your prompt"`')
        return

    prompt = match.group(1).strip()

    # Everything before the quoted prompt contains the options.
    options_text = args[: match.start()].strip().rstrip(",")

    # Parse options by splitting on commas.
    options = [option.strip() for option in options_text.split(",") if option.strip()]

    if not options:
        await ctx.reply("Please provide at least one option.")
        return

    if len(options) > 10:
        await ctx.reply("Please provide no more than 10 options.")
        return

    # Pass data through environment variables to avoid PowerShell quoting issues.
    env = os.environ.copy()
    env["MSGBOX_OPTIONS"] = json.dumps(options, ensure_ascii=False)
    env["MSGBOX_PROMPT"] = prompt

    powershell_script = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$options = ConvertFrom-Json -InputObject $env:MSGBOX_OPTIONS
$prompt = $env:MSGBOX_PROMPT

$form = New-Object System.Windows.Forms.Form
$form.Text = "Network"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(500, 180)
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.TopMost = $true

$label = New-Object System.Windows.Forms.Label
$label.Text = $prompt
$label.Location = New-Object System.Drawing.Point(15, 15)
$label.Size = New-Object System.Drawing.Size(450, 45)
$form.Controls.Add($label)

$flow = New-Object System.Windows.Forms.FlowLayoutPanel
$flow.Location = New-Object System.Drawing.Point(15, 70)
$flow.Size = New-Object System.Drawing.Size(455, 55)
$flow.AutoScroll = $true
$form.Controls.Add($flow)

foreach ($option in $options) {
    $button = New-Object System.Windows.Forms.Button
    $button.Text = [string]$option
    $button.AutoSize = $true
    $button.Margin = New-Object System.Windows.Forms.Padding(4)

    $button.Add_Click({
        $form.Tag = $this.Text
        $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
        $form.Close()
    })

    $flow.Controls.Add($button)
}

[void]$form.ShowDialog()

if ($null -ne $form.Tag) {
    [Console]::Write([string]$form.Tag)
    exit 0
}

exit 2
"""

    def show_popup() -> subprocess.CompletedProcess[str]:
        # The dialog needs its own PowerShell process: the modal dialog blocks
        # until an option is picked and the script ends with `exit`, which
        # would terminate the shared session of src/cmd/shell.py.
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-STA",
                "-Command",
                powershell_script,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=300,
            # The console of the helper process stays invisible.
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    try:
        result = await asyncio.to_thread(show_popup)

        if result.returncode == 2:
            await ctx.reply("Popup closed without selecting an option.")
            return

        if result.returncode != 0:
            print(result.stderr)
            await ctx.reply("Failed to display the popup.")
            return

        selected = result.stdout.strip()
        await ctx.reply(f"User selected: **{selected}**")

    except subprocess.TimeoutExpired:
        await ctx.reply("Popup timed out.")
    except Exception as exc:
        await ctx.reply(f"Error: {type(exc).__name__}: {exc}")
