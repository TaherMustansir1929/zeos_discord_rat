"""Update the running runtime.exe with the latest GitHub release.

Windows locks a running executable, so the update is done in two steps:

1. The bot downloads the newest release and hands the file to a helper.
2. The helper waits for the bot to exit, replaces the executable and starts
   the new version.

The helper is a copy of runtime.exe itself, so nothing extra has to be
shipped next to it and the file name never changes.
"""

import asyncio
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import certifi
import psutil
from discord.ext import commands
from discord.ext.commands import Context

from src.constants import (
    ASSET_NAME,
    GITHUB_OWNER,
    GITHUB_REPO,
    INSTALL_DIR,
    UPDATE_HELPER_FLAG,
)

# Use certifi's trusted certificate bundle for HTTPS.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# The helper runs without a console window and survives the bot process.
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0)

# Seconds the helper waits for the running runtime to exit.
EXIT_TIMEOUT = 120.0


# --------------------------------------------------
# GitHub releases
# --------------------------------------------------


def get_latest_release() -> dict[str, Any]:
    """Return the latest release of the GitHub repository."""
    url = (
        f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
        "/releases/latest"
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "PythonRuntimeUpdater",
            "Accept": "application/vnd.github+json",
        },
    )

    with urllib.request.urlopen(request, context=SSL_CONTEXT, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def find_asset_url(release: dict[str, Any]) -> str | None:
    """Return the download URL of the runtime asset of a release."""
    for item in release.get("assets", []):
        if item.get("name") == ASSET_NAME:
            return item.get("browser_download_url")

    return None


def download_asset(url: str, destination: Path) -> None:
    """Download a release asset to the given path."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "PythonRuntimeUpdater"}
    )

    with (
        urllib.request.urlopen(request, context=SSL_CONTEXT, timeout=120) as response,
        destination.open("wb") as file,
    ):
        shutil.copyfileobj(response, file)


# --------------------------------------------------
# Update helper
# --------------------------------------------------


def helper_requested(argv: list[str]) -> bool:
    """Whether the process was started as the update helper."""
    return bool(argv) and argv[0] == UPDATE_HELPER_FLAG


def helper_command(downloaded: Path) -> list[str]:
    """Return the command that starts the update helper."""
    if getattr(sys, "frozen", False):
        return [sys.executable, UPDATE_HELPER_FLAG, str(downloaded)]

    return [sys.executable, "-m", "src.utils.updater", str(downloaded)]


def pid_exists(pid: int) -> bool:
    """Whether the process is still running."""
    try:
        return psutil.pid_exists(pid)
    except Exception:
        return False


def wait_for_exit(pid: int, timeout: float = EXIT_TIMEOUT) -> bool:
    """Wait until the given process is gone."""
    deadline = time.time() + timeout

    while time.time() < deadline:
        if not pid_exists(pid):
            return True

        time.sleep(0.5)

    return False


def install_folder_writable() -> bool:
    """Whether the install folder can be written without elevation."""
    probe = INSTALL_DIR / ".update_write_test"

    try:
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        probe.write_bytes(b"")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def replace_executable(downloaded: Path) -> Path:
    """Replace the installed executable with the downloaded one.

    The file is copied next to the target first, so the final swap happens
    inside one directory and always succeeds. No administrator rights are
    needed as long as the install folder is writable by the current user.
    """
    install_path = INSTALL_DIR / ASSET_NAME
    staged = install_path.with_name(f"{install_path.stem}.new{install_path.suffix}")

    install_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(downloaded, staged)
    os.replace(staged, install_path)

    return install_path


def run_helper(argv: list[str]) -> int:
    """Replace the running executable and start the new version."""
    if not argv:
        print("[updater] no file to install.")
        return 1

    downloaded = Path(argv[0])
    parent_pid = os.getppid()

    print(f"[updater] waiting for runtime process {parent_pid} to exit...")

    if not wait_for_exit(parent_pid):
        print("[updater] the runtime did not exit in time, nothing was changed.")
        return 1

    try:
        install_path = replace_executable(downloaded)
    except PermissionError:
        print(
            "[updater] no write access to the install folder, "
            "run installer.exe as administrator once to grant it."
        )
        return 1
    except OSError as exc:
        print(f"[updater] could not replace the executable: {exc}")
        return 1
    finally:
        downloaded.unlink(missing_ok=True)

    print(f"[updater] replaced {install_path}, starting the new version...")

    subprocess.Popen(
        [str(install_path)],
        cwd=str(INSTALL_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
        close_fds=True,
    )

    return 0


# --------------------------------------------------
# Bot command
# --------------------------------------------------


async def update_runtime(ctx: Context[commands.Bot]) -> None:
    """Download the latest release and replace the running executable."""
    if not getattr(sys, "frozen", False):
        await ctx.reply("The updater only works for the packaged runtime.exe.")
        return

    # The whole update runs without administrator rights, so the install
    # folder has to be writable by the current user.
    if not install_folder_writable():
        await ctx.reply(
            "The install folder is not writable by this user. "
            "Run installer.exe as administrator once to grant access."
        )
        return

    await ctx.reply("Checking GitHub for the latest release...")

    try:
        release = await asyncio.to_thread(get_latest_release)
    except urllib.error.HTTPError as exc:
        await ctx.reply(f"GitHub returned HTTP {exc.code}: {exc.reason}")
        return
    except Exception as exc:
        await ctx.reply(f"Could not reach GitHub: {exc}")
        return

    tag = release.get("tag_name", "unknown")
    url = find_asset_url(release)

    if not url:
        await ctx.reply(f"{ASSET_NAME} was not found in release {tag}.")
        return

    downloaded = Path(tempfile.gettempdir()) / f"{ASSET_NAME}.{os.getpid()}.update"

    await ctx.reply(f"Downloading {ASSET_NAME} from release {tag}...")

    try:
        await asyncio.to_thread(download_asset, url, downloaded)
    except Exception as exc:
        downloaded.unlink(missing_ok=True)
        await ctx.reply(f"Download failed: {exc}")
        return

    try:
        subprocess.Popen(
            helper_command(downloaded),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
            close_fds=True,
        )
    except Exception as exc:
        downloaded.unlink(missing_ok=True)
        await ctx.reply(f"Could not start the update helper: {exc}")
        return

    await ctx.reply(
        f"Downloaded {ASSET_NAME} from release {tag}. "
        "The runtime restarts in a moment."
    )

    # The executable can only be replaced once this process is gone.
    await asyncio.sleep(1)
    os._exit(0)


def main(argv: list[str]) -> int:
    """Entry point of the standalone helper."""
    return run_helper(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
