import os
import sys

from dotenv import load_dotenv

from bot import bot
from elevation import ensure_admin, prepare_installation, stop_existing_instances

load_dotenv()


def main() -> None:
    if getattr(sys, "frozen", False):
        # PyInstaller's --uac-admin option should normally elevate
        # the executable before Python starts.
        ensure_admin()

        # Avoid copying the Python interpreter when running from source.
        if prepare_installation():
            return

        # Run this before creating the GUI or initializing app state.
        stop_existing_instances()

    # put your token either in env for dev or hardcode for final .exe build
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        token = "<your-bot-token>"

    bot.run(token)


if __name__ == "__main__":
    main()
