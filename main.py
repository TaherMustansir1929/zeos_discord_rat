import os
import sys

from dotenv import load_dotenv

from bot import bot
from src.utils.elevation import stop_existing_instances
from src.utils.updater import helper_requested, run_helper

load_dotenv()


def main() -> None:
    # The update helper replaces the executable and never starts the bot.
    if helper_requested(sys.argv[1:]):
        raise SystemExit(run_helper(sys.argv[2:]))

    if getattr(sys, "frozen", False):
        stop_existing_instances()

    # put your token either in env for dev or hardcode for final .exe build
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        token = ""

    bot.run(token)


if __name__ == "__main__":
    main()
