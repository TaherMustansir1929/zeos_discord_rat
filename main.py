import os
import sys

from dotenv import load_dotenv

from bot import bot
from elevation import stop_existing_instances

load_dotenv()


def main() -> None:
    if getattr(sys, "frozen", False):
        stop_existing_instances()

    # put your token either in env for dev or hardcode for final .exe build
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        token = ""

    bot.run(token)


if __name__ == "__main__":
    main()
