"""Move files onto the host and run the files that already live there."""

import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

import discord
from discord.ext import commands
from discord.ext.commands import Context

# Largest payload that a single push command may write.
MAX_PUSH_SIZE = 100 * 1024 * 1024

# Name of the numbered chunks that together make up one big file.
CHUNK_PATTERN = re.compile(r"^(?P<stem>.+)\.(?P<number>\d{3})$")

# Started programs are kept so Python does not complain about them later.
RUNNING_PROCESSES: list[subprocess.Popen[bytes]] = []


def resolve_destination(destination: str, filename: str) -> Path:
    """Work out where a pushed file has to be written.

    A destination that is an existing folder or that ends with a separator
    keeps the name of the file inside it, every other destination is the
    full path of the file itself.
    """
    cleaned = os.path.expandvars(os.path.expanduser(destination.strip().strip('"')))
    target = Path(cleaned) if cleaned else Path.cwd()

    # Relative paths are resolved from the bot's working directory.
    if not target.is_absolute():
        target = Path.cwd() / target

    # A trailing separator always marks the destination as a folder.
    if cleaned.endswith(("/", "\\")) or target.is_dir():
        target = target / Path(filename).name

    return target


def detect_chunks(attachments: list[discord.Attachment]) -> str | None:
    """Return the shared file name when the attachments are chunks of one file."""
    if len(attachments) < 2:
        return None

    stems: set[str] = set()

    for attachment in attachments:
        match = CHUNK_PATTERN.match(Path(attachment.filename).name)

        if match is None:
            return None

        stems.add(match.group("stem"))

    # Only the chunks of the very same file are joined together.
    if len(stems) != 1:
        return None

    return stems.pop()


def chunk_order(attachment: discord.Attachment) -> tuple[int, str]:
    """Sort the numbered chunks of a file by their number."""
    match = CHUNK_PATTERN.match(Path(attachment.filename).name)
    number = int(match.group("number")) if match else 0

    return number, attachment.filename


def write_bytes(path: Path, data: bytes, mode: str) -> int:
    """Write data into a file and return the number of bytes written."""
    with path.open(mode) as handle:
        return handle.write(data)


async def save_chunks(attachments: list[discord.Attachment], target: Path) -> int:
    """Join the numbered chunks into a single file and return its size."""
    ordered = sorted(attachments, key=chunk_order)
    written = 0

    for index, attachment in enumerate(ordered):
        data = await attachment.read()
        mode = "wb" if index == 0 else "ab"

        written += await asyncio.to_thread(write_bytes, target, data, mode)

    return written


async def push_file(ctx: Context[commands.Bot], destination: str) -> None:
    """Save the attachments of the message onto the host disk.

    A destination that points to a folder keeps the name of the attachment
    inside it and several attachments that are numbered chunks are joined
    into one file.
    """
    attachments = list(ctx.message.attachments)

    if not attachments:
        await ctx.reply("Attach the file you want to push.")
        return

    total_size = sum(attachment.size for attachment in attachments)

    if total_size > MAX_PUSH_SIZE:
        await ctx.reply(
            f"Refusing to push {total_size} bytes, the limit is "
            f"{MAX_PUSH_SIZE} bytes per command."
        )
        return

    try:
        chunk_name = detect_chunks(attachments)

        if chunk_name is not None:
            target = resolve_destination(destination, chunk_name)
            target.parent.mkdir(parents=True, exist_ok=True)

            written = await save_chunks(attachments, target)

            await ctx.reply(f"Wrote {written} bytes to `{target}`.")
            return

        first_target = resolve_destination(destination, attachments[0].filename)
        written = 0

        for index, attachment in enumerate(attachments):
            # The first file takes the destination, the others land next to it.
            target = first_target
            if index > 0:
                target = first_target.parent / Path(attachment.filename).name

            target.parent.mkdir(parents=True, exist_ok=True)

            written += await attachment.save(target)

        await ctx.reply(f"Wrote {written} bytes to `{first_target}`.")

    except Exception as exc:
        print(f"Push file error: {exc}")
        await ctx.reply(f"Could not write the file: {type(exc).__name__}: {exc}")


def keep_process(process: subprocess.Popen[bytes]) -> None:
    """Hold on to a started program so it is not cleaned up by Python."""
    RUNNING_PROCESSES.append(process)

    # Only the recent programs are kept so the list cannot grow forever.
    del RUNNING_PROCESSES[:-50]


async def execute_file(ctx: Context[commands.Bot], path: str) -> None:
    """Run a file that already exists on the host."""
    cleaned = os.path.expandvars(os.path.expanduser(path.strip().strip('"')))
    target = Path(cleaned)

    # Relative paths are resolved from the bot's working directory.
    if not target.is_absolute():
        target = Path.cwd() / target

    if not target.is_file():
        await ctx.reply(f"File not found: `{target}`")
        return

    suffix = target.suffix.lower()

    if suffix in (".exe", ".com"):
        command = [str(target)]
    elif suffix in (".bat", ".cmd"):
        command = ["cmd", "/c", str(target)]
    elif suffix == ".ps1":
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(target),
        ]
    elif suffix == ".py":
        command = [sys.executable, str(target)]
    else:
        # Unknown types are handed to the shell, which reports no process id.
        try:
            await asyncio.to_thread(os.startfile, str(target))
        except Exception as exc:
            print(f"Execute file error: {exc}")
            await ctx.reply(f"Could not start `{target}`: {exc}")
            return

        await ctx.reply(f"Started `{target}` with the default program.")
        return

    try:
        process = await asyncio.to_thread(
            subprocess.Popen,
            command,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        print(f"Execute file error: {exc}")
        await ctx.reply(f"Could not start `{target}`: {exc}")
        return

    keep_process(process)

    await ctx.reply(f"Started `{' '.join(command)}` (pid {process.pid}).")
