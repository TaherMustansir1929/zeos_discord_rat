"""Create the encrypted token line for `main.py`.

Run it from the project folder:

    uv run python tools/encrypt_token.py

The plain token is asked for without an echo, or it can be given on the
command line. The output is a single `ENCRYPTED_TOKEN = "..."` line that
replaces the token in `main.py`. Every run produces a different line.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.token_cipher import encrypt_token  # noqa: E402


def main() -> None:
    if len(sys.argv) > 1:
        token = " ".join(sys.argv[1:]).strip()
    else:
        print("The input is hidden, the token is not shown on the screen.")
        token = getpass.getpass("Bot token: ").strip()

    if not token:
        print("The token is empty, nothing was encrypted.")
        return

    line = encrypt_token(token)
    width = 100

    print()
    print(f"ENCRYPTED_TOKEN = (" + '"' + line[: width] + '"')
    for start in range(width, len(line) + 1, width):
        chunk = line[start : start + width]
        tail = '"' if chunk else ""
        print("    \"" + chunk + (tail if chunk else "\""))

    print(")")
    print()
    print("Paste this line into main.py in the place of the plain token.")


if __name__ == "__main__":
    main()
