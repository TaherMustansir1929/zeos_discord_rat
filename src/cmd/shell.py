import subprocess
import threading

ps: subprocess.Popen[str] = subprocess.Popen(
    ["powershell", "-NoLogo", "-NoExit", "-Command", "-"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
    creationflags=subprocess.CREATE_NO_WINDOW,
)

# Only one command may use the shared PowerShell session at a time.
session_lock = threading.Lock()


def execute_cmd(cmd: str) -> str:
    marker = "__CMD_DONE__"

    wrapped = f"""
    try {{
        {cmd}
    }} catch {{
        Write-Output "$($_.Exception.Message)"
    }}
    """

    if not ps.stdin or not ps.stdout:
        return "ps.stdin or ps.stdout object NOT FOUND"

    with session_lock:
        ps.stdin.write(f"{wrapped}\n")
        ps.stdin.write(f'Write-Output "{marker}"\n')
        ps.stdin.flush()

        output: list[str] = []
        for line in ps.stdout:
            if marker in line:
                break
            output.append(line.rstrip())

    return "\n".join(output)
