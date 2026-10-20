import os

from dotenv import load_dotenv

from bot import bot

load_dotenv()

if __name__ == "__main__":
    # put your token either in env for dev or hardcode for release .exe
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        token = "<your-bot-token>"

    bot.run(token)
