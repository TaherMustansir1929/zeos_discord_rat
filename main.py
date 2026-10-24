import sys

from bot import bot
from src.utils.elevation import stop_existing_instances
from src.utils.token_cipher import decrypt_token
from src.utils.updater import helper_requested, run_helper

ENCRYPTED_TOKEN = None


def main() -> None:
    # The update helper replaces the executable and never starts the bot.
    if helper_requested(sys.argv[1:]):
        raise SystemExit(run_helper(sys.argv[2:]))

    if getattr(sys, "frozen", False):
        stop_existing_instances()

    if not ENCRYPTED_TOKEN:
        print("There is no token in the source. Run tools/builder.py or")
        print("paste the output of tools/encrypt_token.py into main.py.")
        raise SystemExit(1)

    try:
        token = decrypt_token(ENCRYPTED_TOKEN)
    except ValueError as exc:
        print(f"The token of the bot could not be decrypted: {exc}")
        raise SystemExit(1)

    bot.run(token)


if __name__ == "__main__":
    main()
