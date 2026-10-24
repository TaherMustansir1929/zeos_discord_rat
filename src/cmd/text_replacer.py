"""Replace typed sequences with other text while the user is typing.

The script watches the keyboard and swaps every configured sequence for its
replacement as soon as it is typed. The rules are stored in
`replacements.json` in the current working directory and are reloaded
whenever that file changes, so the Discord bot can update them at runtime.

There are no built in rules: without a `replacements.json` file nothing is
replaced.

Run it on its own with:

    python src/cmd/text_replacer.py
"""

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import pyperclip
from discord.ext import commands
from discord.ext.commands import Context

# Configuration file written by the bot.
REPLACEMENTS_FILE = Path("replacements.json")
# Seconds between two checks of the configuration file.
RELOAD_INTERVAL = 1.0


def read_replacements(path: Path) -> dict[str, str]:
    """Read the replacement rules from the configuration file."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    if not isinstance(raw, dict):
        return {}

    return {
        key: value
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, str) and key
    }


def write_replacements(path: Path, replacements: dict[str, str]) -> None:
    """Write the rules to the configuration file.

    The file is replaced in one step so a running script never reads a
    half written configuration.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(
        json.dumps(replacements, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    os.replace(temp_path, path)


class TextReplacer:
    """Swaps typed sequences for their replacement while typing."""

    def __init__(
        self,
        config_path: Path = REPLACEMENTS_FILE,
    ) -> None:
        # Imported here so the Discord bot can use this module without
        # pulling in the keyboard hook.
        from pynput.keyboard import Controller, Key

        self.key = Key
        self.controller = Controller()
        self.modifiers = {
            Key.ctrl,
            Key.ctrl_l,
            Key.ctrl_r,
            Key.alt,
            Key.alt_l,
            Key.alt_r,
            Key.cmd,
            Key.cmd_l,
            Key.cmd_r,
            Key.shift,
            Key.shift_l,
            Key.shift_r,
        }

        self.config_path = config_path
        self.rules: dict[str, str] = self.load_rules()
        self.word_buffer = ""
        self.busy = False
        self.listener: Any = None
        self.stopped = threading.Event()

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------
    def load_rules(self) -> dict[str, str]:
        """Return the configured rules.

        Without a `replacements.json` file there are no rules at all, so
        nothing is replaced.
        """
        return read_replacements(self.config_path)

    def watch_rules(self) -> None:
        """Reload the rules whenever the configuration file changes."""
        stamp = self.file_stamp()

        while not self.stopped.wait(RELOAD_INTERVAL):
            current = self.file_stamp()

            if current == stamp:
                continue

            stamp = current
            rules = self.load_rules()

            if rules != self.rules:
                self.rules = rules
                print(f"[+] Loaded {len(rules)} replacement rule(s).")

    def file_stamp(self) -> float | None:
        """Return the modification time of the configuration file."""
        try:
            return self.config_path.stat().st_mtime
        except OSError:
            return None

    # ------------------------------------------------------------------
    # Replacement
    # ------------------------------------------------------------------
    def replace_match(self, match: str) -> None:
        """Replace the just typed sequence using a clipboard paste."""
        replacement = self.rules[match]
        self.busy = True

        try:
            try:
                old_clipboard = pyperclip.paste()
            except Exception:
                old_clipboard = ""

            try:
                pyperclip.copy(replacement)

                # Remove the matched characters.
                for _ in match:
                    self.controller.press(self.key.backspace)
                    self.controller.release(self.key.backspace)

                # Paste the replacement text.
                with self.controller.pressed(self.key.ctrl):
                    self.controller.press("v")
                    self.controller.release("v")

                # Give the application time to process the paste.
                time.sleep(0.15)

            finally:
                # Restore the previous clipboard contents.
                pyperclip.copy(old_clipboard)

            self.word_buffer = self.word_buffer[: -len(match)] + replacement

        finally:
            self.busy = False

    def on_press(self, key) -> None:
        """Handle a single key press."""
        if self.busy:
            return

        # Shortcuts may change the meaning or the location of the typed text.
        if key in self.modifiers:
            self.word_buffer = ""
            return

        if key == self.key.backspace:
            self.word_buffer = self.word_buffer[:-1]
            return

        if key == self.key.esc:
            self.word_buffer = ""
            self.stop()
            return

        if key in (self.key.enter, self.key.tab):
            self.word_buffer = ""
            return

        if key in (
            self.key.left,
            self.key.right,
            self.key.up,
            self.key.down,
            self.key.home,
            self.key.end,
            self.key.page_up,
            self.key.page_down,
        ):
            self.word_buffer = ""
            return

        char = getattr(key, "char", None)

        if not char:
            return

        # A non word character ends the current word.
        if not char.isalnum() and char != "_":
            self.word_buffer = ""
            return

        max_length = max((len(word) for word in self.rules), default=1)
        self.word_buffer = (self.word_buffer + char)[-max_length:]

        # The sequence is replaced as soon as it is complete.
        for word in self.rules:
            if self.word_buffer.lower().endswith(word.lower()):
                self.replace_match(word)
                break

    # ------------------------------------------------------------------
    # Life cycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start watching the keyboard."""
        from pynput import keyboard

        if self.listener is not None:
            return

        self.stopped.clear()
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

        threading.Thread(target=self.watch_rules, daemon=True).start()

    def stop(self) -> None:
        """Stop watching the keyboard."""
        self.stopped.set()

        if self.listener is not None:
            self.listener.stop()
            self.listener = None

    @property
    def running(self) -> bool:
        """Whether the keyboard is currently being watched."""
        return self.listener is not None


def rules_error(rules: object) -> str | None:
    """Return an error message when the rules cannot be used."""
    if not isinstance(rules, dict):
        return "The rules must be a JSON object."

    if not rules:
        return 'Give at least one rule, for example {"love": "hate"}.'

    for key, value in rules.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return (
                "Every rule must be a pair of strings, "
                'for example {"love": "hate"}.'
            )

        if not key:
            return "A rule cannot have an empty key."

    return None


async def set_replacements(
    ctx: Context[commands.Bot],
    replacements: dict[str, str],
    path: Path = REPLACEMENTS_FILE,
) -> None:
    """Store the replacement rules used by the text replacer."""
    error = rules_error(replacements)

    if error:
        await ctx.reply(error)
        return

    try:
        write_replacements(path, replacements)
    except OSError as exc:
        await ctx.reply(f"Could not save the rules: {exc}")
        return

    preview = ", ".join(f"{key} -> {value}" for key, value in list(replacements.items())[:5])
    await ctx.reply(
        f"Saved {len(replacements)} replacement rule(s) to `{path.name}`.\n{preview}"
    )


async def add_replacements(
    ctx: Context[commands.Bot],
    replacements: dict[str, str],
    path: Path = REPLACEMENTS_FILE,
) -> None:
    """Add rules to the configuration file, keeping the existing ones."""
    error = rules_error(replacements)

    if error:
        await ctx.reply(error)
        return

    rules = read_replacements(path)
    rules.update(replacements)

    try:
        write_replacements(path, rules)
    except OSError as exc:
        await ctx.reply(f"Could not save the rules: {exc}")
        return

    preview = ", ".join(f"{key} -> {value}" for key, value in list(replacements.items())[:5])
    await ctx.reply(
        f"Added {len(replacements)} rule(s) to `{path.name}`.\n"
        f"{preview}\n"
        f"The file now holds {len(rules)} rule(s)."
    )


async def remove_replacement(
    ctx: Context[commands.Bot], key: str, path: Path = REPLACEMENTS_FILE
) -> None:
    """Remove a single rule from the configuration file."""
    if not key:
        await ctx.reply("Give the key of the rule to remove.")
        return

    rules = read_replacements(path)

    if key not in rules:
        await ctx.reply(f"There is no rule for `{key}`.")
        return

    del rules[key]

    try:
        write_replacements(path, rules)
    except OSError as exc:
        await ctx.reply(f"Could not save the rules: {exc}")
        return

    await ctx.reply(
        f"Removed `{key}`. The file now holds {len(rules)} rule(s)."
    )


async def clear_replacements(
    ctx: Context[commands.Bot], path: Path = REPLACEMENTS_FILE
) -> None:
    """Delete the whole configuration file."""
    try:
        path.unlink()
    except FileNotFoundError:
        await ctx.reply(f"There is no `{path.name}` to delete.")
        return
    except OSError as exc:
        await ctx.reply(f"Could not delete the rules: {exc}")
        return

    await ctx.reply(f"Deleted `{path.name}`. No rules are active.")


# The replacer that runs inside the bot process.
replacer: TextReplacer | None = None


def current_replacer() -> TextReplacer | None:
    """Return the replacer that runs inside the bot process."""
    return replacer


def active_rules() -> dict[str, str]:
    """Return the rules of the running replacer, or the ones on disk."""
    instance = current_replacer()

    if instance is not None:
        return instance.rules

    return read_replacements(REPLACEMENTS_FILE)


async def start_text_replacer(ctx: Context[commands.Bot]) -> None:
    """Start the text replacer on this machine."""
    global replacer

    if replacer is not None and replacer.running:
        await ctx.reply("The text replacer is already running.")
        return

    try:
        replacer = TextReplacer()
        replacer.start()
    except Exception as exc:
        replacer = None
        await ctx.reply(f"Could not start the text replacer: {exc}")
        return

    await ctx.reply(f"Text replacer started with {len(replacer.rules)} rule(s).")


async def stop_text_replacer(ctx: Context[commands.Bot]) -> None:
    """Stop the text replacer on this machine."""
    global replacer

    if replacer is None or not replacer.running:
        await ctx.reply("The text replacer is not running.")
        return

    replacer.stop()
    replacer = None

    await ctx.reply("Text replacer stopped.")


def main() -> None:
    """Run the text replacer until it is stopped."""
    instance = TextReplacer()
    instance.start()

    print("Text replacer is running. Press ESC to exit.")
    print(f"Rules file: {instance.config_path.resolve()}")

    try:
        while instance.running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        instance.stop()


if __name__ == "__main__":
    main()
