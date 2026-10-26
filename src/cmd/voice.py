import asyncio
import subprocess

from discord.ext import commands
from discord.ext.commands import Context


async def voice_api(ctx: Context[commands.Bot], text: str) -> None:
    text = text.strip()

    if not text:
        await ctx.reply("Please provide some text to speak.")
        return

    # Limit input to prevent excessively long speech.
    if len(text) > 500:
        await ctx.reply("Text must be 500 characters or fewer.")
        return

    # PowerShell receives the text through stdin, not as executable code.
    script = r"""
Add-Type -AssemblyName System.Speech
$reader = [System.IO.StreamReader]::new([Console]::OpenStandardInput())
$text = $reader.ReadToEnd()
$reader.Dispose()

$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $speaker.Speak($text)
}
finally {
    $speaker.Dispose()
}
"""

    try:
        await ctx.send("Speaking...")

        # The speech needs its own PowerShell process: the script reads the
        # text from stdin, which in the shared session of src/cmd/shell.py
        # would swallow the queued commands instead.
        process = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            # The console of the helper process stays invisible.
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        try:
            _, stderr = await asyncio.wait_for(
                process.communicate(input=text.encode("utf-8")),
                timeout=60,
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            await ctx.send("Speech timed out.")
            return

        if process.returncode != 0:
            await ctx.send("Windows text-to-speech failed.")
            print((stderr or b"").decode("utf-8", errors="replace"))

    except Exception as exc:
        print(f"Speech error: {exc}")
        await ctx.send("Could not start text-to-speech.")
