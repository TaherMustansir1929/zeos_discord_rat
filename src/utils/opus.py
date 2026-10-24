"""Load the opus library that the Discord voice connection needs.

Python does not ship the opus library, but the discord package does. The
library is searched in the discord package, next to the executable, in the
install folder and on the PATH, so a packaged runtime keeps working.
"""

import os
import struct
import sys
from pathlib import Path

import discord
import discord.opus

from src.constants import INSTALL_DIR, OPUS_LIBRARY_NAMES


def opus_folders() -> list[Path]:
    """Return the folders that are searched for the opus library.

    A library that was placed next to the executable or into the working
    directory comes first, so it can be replaced without a new build.
    """
    folders: list[Path] = []

    # The folder of the running executable and the working directory, this
    # is where a hand placed library is found.
    folders.append(Path(sys.executable).parent)
    folders.append(Path.cwd())

    # The library is shipped inside the discord package.
    package_folder = Path(discord.__file__).parent
    folders.append(package_folder / "bin")
    folders.append(package_folder)

    # A frozen build keeps the collected binaries in the bundle folder.
    bundle_folder = getattr(sys, "_MEIPASS", None)
    if bundle_folder:
        folders.append(Path(bundle_folder))
        folders.append(Path(bundle_folder) / "discord" / "bin")

    # The folder the runtime is installed in.
    folders.append(INSTALL_DIR)

    # Every folder of the PATH, the loader searches them as well.
    folders.extend(Path(entry) for entry in os.environ.get("PATH", "").split(os.pathsep))

    return [folder for folder in folders if folder.is_dir()]


def opus_library_name() -> str:
    """Return the name of the opus library for this interpreter."""
    bits = struct.calcsize("P") * 8
    return f"libopus-0.x{'64' if bits > 32 else '86'}.dll"


def ensure_opus() -> Path | None:
    """Load the opus library and return the file it was loaded from.

    Returns None when the library is already loaded or when it cannot be
    found, the voice features then report the problem to the user.
    """
    if discord.opus.is_loaded():
        return None

    names = [opus_library_name(), *OPUS_LIBRARY_NAMES]

    for folder in opus_folders():
        for name in names:
            candidate = folder / name

            if not candidate.is_file():
                continue

            try:
                discord.opus.load_opus(str(candidate))
            except Exception as exc:
                print(f"Could not load opus from {candidate}: {exc}")
                continue

            return candidate

    # The loader of Windows also looks into the folders of the PATH.
    try:
        discord.opus.load_opus(opus_library_name())
    except Exception as exc:
        print(f"Could not load the opus library: {exc}")
        return None

    return Path(opus_library_name())
