import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

import certifi

from src.constants import (
    APP_DIR,
    ASSET_NAME,
    GITHUB_OWNER,
    GITHUB_REPO,
    INSTALL_DIR,
)

# ================= CONFIGURATION =================

# The runtime is installed in C:\PythonRuntime.
INSTALL_PATH = INSTALL_DIR / ASSET_NAME

STARTUP_DIR = os.path.join(
    os.environ.get("ProgramData", r"C:\ProgramData"),
    r"Microsoft\Windows\Start Menu\Programs\Startup",
)

STARTUP_SHORTCUT = os.path.join(STARTUP_DIR, f"{APP_DIR}.lnk")

# Use certifi's trusted certificate bundle for HTTPS.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# =================================================


def log(message):
    print(f"[PythonRuntime Installer] {message}", flush=True)


def download_file(url, destination):
    request = urllib.request.Request(
        url, headers={"User-Agent": "PythonRuntimeInstaller"}
    )

    with urllib.request.urlopen(request, context=SSL_CONTEXT, timeout=60) as response:
        with open(destination, "wb") as file:
            shutil.copyfileobj(response, file)


def get_latest_release():
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "PythonRuntimeInstaller",
            "Accept": "application/vnd.github+json",
        },
    )

    with urllib.request.urlopen(request, context=SSL_CONTEXT, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def stop_runtime():
    log("Checking for running runtime.exe processes...")

    subprocess.run(
        ["taskkill", "/F", "/T", "/IM", "runtime.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

    time.sleep(1)
    log("Process shutdown check completed.")


def create_startup_shortcut():
    os.makedirs(STARTUP_DIR, exist_ok=True)

    # Use Windows Script Host to create a standard .lnk shortcut.
    powershell_script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{STARTUP_SHORTCUT}'); "
        f"$s.TargetPath = '{INSTALL_PATH}'; "
        f"$s.WorkingDirectory = '{INSTALL_DIR}'; "
        "$s.Save()"
    )

    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            powershell_script,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    log("Startup shortcut created.")


def grant_user_access():
    """Let the current user replace the executable without elevation.

    The runtime updates itself in the background with the rights of the user
    that started it, so the install folder has to be writable for them.
    """
    username = os.environ.get("USERNAME", "")
    domain = os.environ.get("USERDOMAIN", "")
    account = f"{domain}\\{username}" if domain and username else username

    if not account:
        return

    subprocess.run(
        [
            "icacls",
            str(INSTALL_DIR),
            "/grant",
            f"{account}:(OI)(CI)M",
            "/T",
            "/Q",
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    log("Access granted to the current user.")


def install():
    if os.name != "nt":
        log("ERROR: This installer only supports Windows.")
        return False

    if "YOUR_GITHUB_USERNAME" in GITHUB_OWNER:
        log("ERROR: Configure GITHUB_OWNER and GITHUB_REPO first.")
        return False

    temporary_path = os.path.join(
        os.environ.get("TEMP", str(INSTALL_DIR)), "runtime_download.exe"
    )

    try:
        log("Retrieving latest GitHub release...")

        release = get_latest_release()

        log(f"Latest release: {release.get('tag_name', 'unknown')}")

        asset = next(
            (
                item
                for item in release.get("assets", [])
                if item.get("name") == ASSET_NAME
            ),
            None,
        )

        if not asset:
            log(f"ERROR: {ASSET_NAME} was not found in the release.")
            return False

        download_url = asset["browser_download_url"]

        log("Downloading runtime.exe...")

        download_file(download_url, temporary_path)

        log("Download completed.")

        # Stop the existing program before replacing it.
        stop_runtime()

        os.makedirs(INSTALL_DIR, exist_ok=True)

        log(f"Installing to: {INSTALL_PATH}")

        shutil.move(temporary_path, INSTALL_PATH)

        log("Installation completed.")

        # The runtime updates itself later without administrator rights.
        grant_user_access()

        create_startup_shortcut()

        log("Starting runtime.exe...")

        subprocess.Popen([INSTALL_PATH], cwd=INSTALL_DIR)

        log("Runtime started successfully.")
        return True

    except urllib.error.HTTPError as error:
        log(f"ERROR: GitHub returned HTTP {error.code}: {error.reason}")

    except urllib.error.URLError as error:
        log(f"ERROR: Could not retrieve release or download file: {error}")

    except Exception as error:
        log(f"ERROR: {error}")

    finally:
        if os.path.exists(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError:
                pass

    return False


if __name__ == "__main__":
    log("Installer started.")

    if not install():
        log("Installation failed.")
        input("Press Enter to exit...")
        sys.exit(1)

    log("Installer finished.")
