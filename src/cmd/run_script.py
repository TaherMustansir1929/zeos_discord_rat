import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import aiohttp
from discord.ext import commands
from discord.ext.commands import Context

from src.cmd.shell import execute_cmd
from src.utils.utils import send_text_in_chunks

# Command templates used to launch a saved script. "{path}" is replaced with the
# quoted path of the script and "{python}" with the Python interpreter.
SCRIPT_COMMANDS: dict[str, str] = {
    ".ps1": (
        "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File {path}"
    ),
    ".bat": "& {path}",
    ".cmd": "& {path}",
    ".exe": "& {path}",
    ".com": "& {path}",
    ".py": "& {python} {path}",
    ".vbs": "cscript.exe //nologo {path}",
    ".js": "cscript.exe //nologo {path}",
}

SUPPORTED_EXTENSIONS = ", ".join(sorted(SCRIPT_COMMANDS))


def quote_ps(value: str) -> str:
    """Quote a value so PowerShell treats it as a literal string."""
    return "'" + value.replace("'", "''") + "'"


def python_interpreter() -> str:
    """Return the interpreter used to run .py scripts."""
    # A frozen build cannot re-use its own executable to run scripts.
    if getattr(sys, "frozen", False):
        return "python"
    return quote_ps(sys.executable)


def resolve_destination(destination: str, filename: str) -> Path:
    """Resolve where the script is stored.

    A destination that is an existing folder (or that has no extension) keeps
    the original file name inside that folder, otherwise the destination is
    used as the full path of the script.
    """
    cleaned = os.path.expandvars(os.path.expanduser(destination.strip().strip('"')))
    target = Path(cleaned)

    # Relative paths are resolved from the bot's working directory.
    if not target.is_absolute():
        target = Path.cwd() / target

    if target.is_dir() or not target.suffix:
        target = target / filename

    return target.resolve()


def build_run_command(script_path: Path) -> str | None:
    """Build the PowerShell command that runs the given script.

    Returns None when the script type has no known launcher.
    """
    template = SCRIPT_COMMANDS.get(script_path.suffix.lower())

    if template is None:
        return None

    runner = template.format(
        path=quote_ps(str(script_path)),
        python=python_interpreter(),
    )

    # The script runs in its own folder and the exit code is reported back.
    return (
        f"Push-Location {quote_ps(str(script_path.parent))}; "
        f"{runner}; "
        'Write-Output "Exit code: $LASTEXITCODE"; '
        "Pop-Location"
    )


def url_filename(url: str) -> str:
    """Derive a file name from the path part of a URL."""
    return Path(unquote(urlparse(url).path)).name or "script.ps1"


async def download_script(url: str, target: Path) -> None:
    """Download a script from a URL and store it at the target path."""
    parsed = urlparse(url)

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Please provide a valid HTTP/HTTPS script URL.")

    timeout = aiohttp.ClientTimeout(total=60)

    async with (
        aiohttp.ClientSession(timeout=timeout) as session,
        session.get(url, allow_redirects=False) as response,
    ):
        if response.status != 200:
            raise ValueError(f"Download failed (HTTP {response.status}).")

        with target.open("wb") as output:
            async for chunk in response.content.iter_chunked(65536):
                output.write(chunk)


async def run_script_file(
    ctx: Context[commands.Bot],
    destination: str,
    source: str | None = None,
) -> None:
    """Store a Windows script on the host and run it.

    The script is taken from the attachment of the command message, or
    downloaded from `source` when a URL is given. It is saved at
    `destination` and then executed through the shared PowerShell session.

    The extension of the saved file decides how the script is executed.
    """
    attachment = ctx.message.attachments[0] if ctx.message.attachments else None
    url = source

    if attachment is not None:
        filename = Path(attachment.filename).name or "script.ps1"
    elif url:
        filename = url_filename(url)
    else:
        await ctx.reply(
            "Attach a script to the message or provide a direct URL to one.\n"
            f"Supported types: {SUPPORTED_EXTENSIONS}"
        )
        return

    try:
        target = resolve_destination(destination, filename)
        target.parent.mkdir(parents=True, exist_ok=True)

        if attachment is not None:
            await attachment.save(target)
        elif url:
            await download_script(url, target)
        else:
            raise ValueError("No script to run.")

    except Exception as exc:
        print(f"Script save error: {exc}")
        await ctx.reply(f"Could not save the script: {type(exc).__name__}: {exc}")
        return

    command = build_run_command(target)

    if command is None:
        await ctx.reply(
            f"Unsupported script type `{target.suffix or '(none)'}`. "
            f"Supported types: {SUPPORTED_EXTENSIONS}"
        )
        return

    await ctx.reply(f"Saved `{target.name}` to `{target.parent}`. Running it...")

    # execute_cmd blocks on the PowerShell pipe, so keep it off the event loop.
    output = await asyncio.to_thread(execute_cmd, command)

    await send_text_in_chunks(ctx, output.strip() or "(the script produced no output)")
