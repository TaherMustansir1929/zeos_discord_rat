"""Remote file browser that keeps a working directory between commands."""

import asyncio
import os
from pathlib import Path

from discord.ext import commands
from discord.ext.commands import Context

from src.utils.utils import send_text_in_chunks

# The directory every browser command starts from.
CURRENT_DIRECTORY = Path.home()

# Bounds of the tree command so a huge folder cannot flood the channel.
MIN_TREE_DEPTH = 1
MAX_TREE_DEPTH = 6
MAX_TREE_ENTRIES = 500


def current_directory() -> Path:
    """Return the directory the browser currently works in."""
    return CURRENT_DIRECTORY


def set_current_directory(path: Path) -> None:
    """Set the directory the browser works in."""
    global CURRENT_DIRECTORY

    CURRENT_DIRECTORY = path


def read_directory(directory: Path) -> list[tuple[str, bool]]:
    """Return the names inside a directory with a flag telling which are folders."""
    entries: list[tuple[str, bool]] = []

    for entry in directory.iterdir():
        try:
            is_directory = entry.is_dir()
        except OSError:
            # A broken link is still worth showing in the listing.
            is_directory = False

        entries.append((entry.name, is_directory))

    return entries


async def show_pwd(ctx: Context[commands.Bot]) -> None:
    """Reply with the directory the browser currently works in."""
    await ctx.reply(f"Current directory: `{current_directory()}`")


async def list_directory(ctx: Context[commands.Bot]) -> None:
    """List the entries of the current directory."""
    directory = current_directory()

    try:
        entries = await asyncio.to_thread(read_directory, directory)
    except OSError as exc:
        print(f"List directory error: {exc}")
        await ctx.reply(f"Could not read `{directory}`: {exc}")
        return

    if not entries:
        await ctx.reply(f"`{directory}` is empty.")
        return

    # Folders come first so the interesting parts are easy to spot.
    folders = sorted(
        (name for name, is_directory in entries if is_directory),
        key=str.lower,
    )
    files = sorted(
        (name for name, is_directory in entries if not is_directory),
        key=str.lower,
    )

    lines = [f"{name}/" for name in folders]
    lines += list(files)

    body = "\n".join(f"  {line}" for line in lines)
    text = f"`{directory}` - {len(entries)} entries\n```\n{body}\n```"

    await send_text_in_chunks(ctx, text)


async def change_directory(ctx: Context[commands.Bot], path: str) -> None:
    """Move the browser working directory to another path."""
    cleaned = os.path.expandvars(os.path.expanduser(path.strip().strip('"')))

    if not cleaned:
        await ctx.reply("Usage: `!cd <path>`")
        return

    current = current_directory()

    if cleaned == "..":
        target = current.parent
    else:
        candidate = Path(cleaned)
        # A relative path is taken from the current directory.
        target = candidate if candidate.is_absolute() else current / candidate

    # Normalising drops the ".." segments so the root of the drive is kept.
    target = Path(os.path.normpath(str(target)))

    if not await asyncio.to_thread(target.is_dir):
        await ctx.reply(f"Directory not found: `{target}`")
        return

    set_current_directory(target)

    await ctx.reply(f"Changed directory to `{target}`")


def build_tree(directory: Path, depth: int) -> tuple[list[str], bool]:
    """Render an ASCII tree of a directory and report whether the cap was hit."""
    lines: list[str] = [str(directory)]
    visited = 0
    truncated = False

    def walk(folder: Path, prefix: str, level: int) -> None:
        nonlocal visited, truncated

        if truncated:
            return

        try:
            children = read_directory(folder)
        except OSError:
            return

        folders = sorted(
            (name for name, is_directory in children if is_directory),
            key=str.lower,
        )
        files = sorted(
            (name for name, is_directory in children if not is_directory),
            key=str.lower,
        )
        ordered = [(name, True) for name in folders]
        ordered += [(name, False) for name in files]

        for index, (name, is_directory) in enumerate(ordered):
            if visited >= MAX_TREE_ENTRIES:
                truncated = True
                return

            visited += 1

            last = index == len(ordered) - 1
            connector = "└── " if last else "├── "
            suffix = "/" if is_directory else ""

            lines.append(f"{prefix}{connector}{name}{suffix}")

            if not is_directory or level >= depth:
                continue

            child_prefix = prefix + ("    " if last else "│   ")

            walk(folder / name, child_prefix, level + 1)

    walk(directory, "", 1)

    return lines, truncated


async def show_tree(ctx: Context[commands.Bot], depth: int = 3) -> None:
    """Render an ASCII tree of the current directory."""
    try:
        levels = int(depth)
    except (TypeError, ValueError):
        levels = 3

    # The tree is clamped so a deep folder cannot produce a huge message.
    levels = max(MIN_TREE_DEPTH, min(MAX_TREE_DEPTH, levels))

    directory = current_directory()

    try:
        lines, truncated = await asyncio.to_thread(build_tree, directory, levels)
    except OSError as exc:
        print(f"Tree error: {exc}")
        await ctx.reply(f"Could not read `{directory}`: {exc}")
        return

    body = "\n".join(lines)

    if truncated:
        body += f"\n... stopped after {MAX_TREE_ENTRIES} entries"

    await send_text_in_chunks(ctx, f"Tree of `{directory}`:\n```\n{body}\n```")
