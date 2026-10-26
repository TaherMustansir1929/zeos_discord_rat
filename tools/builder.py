"""Build the runtime executable and inject the token out of the .env file.

    uv run python tools/builder.py

The script does four things in order:

1. It reads the `DISCORD_TOKEN` of the .env file in the project folder.
2. It encrypts the token and puts the encrypted line into `main.py`.
3. It runs the build command of `README.md` that makes `runtime.exe`.
4. It removes the encrypted line from `main.py` again, no matter whether
   the build succeeded, so the source never keeps a token.
"""

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MAIN_FILE = ROOT / "main.py"
ENV_FILE = ROOT / ".env"
README_FILE = ROOT / "README.md"

# The names of the .env keys that are accepted for the token.
TOKEN_NAMES = ("DISCORD_TOKEN", "TOKEN", "BOT_TOKEN")

# The assignment of the token in main.py. The first form is the block
# that carries a token, the second is the comment with `None` that stays
# in the source between two builds.
MAIN_PLACEHOLDER = "ENCRYPTED_TOKEN = None"

TOKEN_BLOCK = re.compile(r"ENCRYPTED_TOKEN = \([\s\S]*?\n\)")
PLACEHOLDER_BLOCK = re.compile(re.escape(MAIN_PLACEHOLDER))


def read_token() -> str:
    """Read the token of the bot out of the .env file."""
    if not ENV_FILE.is_file():
        print(f"The file {ENV_FILE.name} does not exist.")
        print("Create it with the line DISCORD_TOKEN=<token>.")
        raise SystemExit(1)

    seen: dict[str, str] = {}

    for number, raw in enumerate(ENV_FILE.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        name, _, value = line.partition("=")
        seen[name.strip().upper()] = value.strip().strip("\"'")

    for name in TOKEN_NAMES:
        if seen.get(name):
            return seen[name]

    print(f"None of the keys {', '.join(TOKEN_NAMES)} is filled in {ENV_FILE.name}.")
    raise SystemExit(1)


def format_assignment(line: str) -> str:
    """Turn the encoded line into the assignment block of main.py."""
    width = 100

    if len(line) <= width:
        return f'ENCRYPTED_TOKEN = "{line}"'

    parts = [f'ENCRYPTED_TOKEN = ("{line[:width]}"']
    parts += [
        f'    "{line[start : start + width]}"'
        for start in range(width, len(line), width)
    ]
    parts.append(")")

    return "\n".join(parts)


def inject_token(line: str) -> None:
    """Put the encrypted line into main.py."""
    source = MAIN_FILE.read_text(encoding="utf-8")
    replacement = format_assignment(line)

    if not (TOKEN_BLOCK.search(source) or PLACEHOLDER_BLOCK.search(source)):
        print("main.py contains no ENCRYPTED_TOKEN place.")
        raise SystemExit(1)

    # A lambda keeps every character of the encoded line as it is, a
    # plain text replacement would read the backslashes as regex forms.
    updated = TOKEN_BLOCK.sub(lambda _match: replacement, source)
    updated = PLACEHOLDER_BLOCK.sub(
        lambda _match: replacement, updated if updated != source else source
    )

    if updated == source:
        print("The token could not be put into main.py.")
        raise SystemExit(1)

    MAIN_FILE.write_text(updated, encoding="utf-8")
    print("The encrypted token was put into main.py.")


def remove_token() -> None:
    """Remove the encrypted line from main.py again."""
    source = MAIN_FILE.read_text(encoding="utf-8")
    cleaned = TOKEN_BLOCK.sub(lambda _match: MAIN_PLACEHOLDER, source)

    if cleaned != source:
        MAIN_FILE.write_text(cleaned, encoding="utf-8")
        print("The encrypted token was removed from main.py.")
    else:
        print("main.py already holds the state without a token.")


def build_command() -> list[str]:
    return [
        "uv",
        "run",
        "pyinstaller",
        "--clean",
        "--onefile",
        "--noconsole",
        "--paths",
        "src",
        "--collect-data",
        "certifi",
        "--add-binary",
        os.path.join("resources", "libopus-0.x64.dll") + ";discord/bin",
        "--upx-dir",
        "resources",
        "--name",
        "runtime",
        "main.py",
    ]


def run_build() -> int:
    """Run the build of the README and report the output."""
    command = build_command()

    print("Build command:")
    print("  " + subprocess.list2cmdline(command))
    print()

    return subprocess.run(command, check=False, cwd=ROOT).returncode


def main() -> None:
    token = read_token()

    sys.path.insert(0, str(ROOT))

    from src.utils.token_cipher import decrypt_token, encrypt_token

    line = encrypt_token(token)

    # The circle has to work before the build is started.
    if decrypt_token(line) != token:
        print("The encryption of the token does not round-trip, the build stops.")
        raise SystemExit(1)

    # A build that was ended while it ran can leave the encrypted token
    # behind, the new build starts from the clean state.
    if TOKEN_BLOCK.search(MAIN_FILE.read_text(encoding="utf-8")):
        print("main.py still held the token of a build that did not end cleanly.")
        remove_token()

    try:
        inject_token(line)
        code = run_build()
    finally:
        remove_token()

    exe = ROOT / "dist" / "runtime.exe"

    if code == 0:
        if exe.is_file():
            print(
                f"\nThe build succeeded, {exe.name} is in the dist folder "
                f"({exe.stat().st_size / (1024 * 1024):.1f} MB)."
            )
        else:
            print("\nThe build reported success but dist/runtime.exe is missing.")

        print("The plain token is nowhere in the source.")
    else:
        print(f"\nThe build failed with the code {code}.")
        raise SystemExit(code)


if __name__ == "__main__":
    main()
