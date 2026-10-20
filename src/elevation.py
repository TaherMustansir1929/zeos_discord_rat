import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

import psutil

from src.constants import APP_NAME

# --------------------------------------------------
# Configuration
# --------------------------------------------------

EXE_NAME = f"{APP_NAME}.exe"
TASK_NAME = APP_NAME

PROGRAM_FILES = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))

INSTALL_DIR = PROGRAM_FILES / APP_NAME
INSTALL_EXE = INSTALL_DIR / EXE_NAME

MB_YESNO = 0x00000004
MB_ICONQUESTION = 0x00000020
MB_ICONERROR = 0x00000010
MB_OK = 0x00000000
IDYES = 6


# --------------------------------------------------
# Windows utility functions
# --------------------------------------------------


def show_message(message: str, title: str = APP_NAME) -> None:
    ctypes.windll.user32.MessageBoxW(None, message, title, MB_OK)


def show_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(
        None, message, f"{APP_NAME} Error", MB_OK | MB_ICONERROR
    )


def is_admin() -> bool:
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def ensure_admin() -> None:
    """Relaunch the executable through Windows UAC if necessary."""
    if is_admin():
        return

    # This code is primarily intended for a PyInstaller executable.
    # Include script arguments if the application is launched directly.
    if getattr(sys, "frozen", False):
        program = sys.executable
        arguments = sys.argv[1:]
    else:
        program = sys.executable
        arguments = [str(Path(__file__).resolve()), *sys.argv[1:]]

    params = subprocess.list2cmdline(arguments)

    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        program,
        params,
        None,
        1,
    )

    if result <= 32:
        raise SystemExit("Administrator privileges were not granted.")

    # Let the elevated process continue instead.
    raise SystemExit(0)


def same_path(path1: Path, path2: Path) -> bool:
    """Compare Windows paths without case sensitivity."""
    return os.path.normcase(os.path.abspath(str(path1))) == (
        os.path.normcase(os.path.abspath(str(path2)))
    )


def startup_task_exists() -> bool:
    result = subprocess.run(
        [
            "schtasks.exe",
            "/Query",
            "/TN",
            TASK_NAME,
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    return result.returncode == 0


# --------------------------------------------------
# Startup registration
# --------------------------------------------------


def register_startup_task() -> None:
    """Create or update the visible {APP_NAME} scheduled task."""
    if not INSTALL_EXE.is_file():
        raise FileNotFoundError(f"Installed executable was not found: {INSTALL_EXE}")

    command = [
        "schtasks.exe",
        "/Create",
        "/TN",
        TASK_NAME,
        "/SC",
        "ONLOGON",
        "/TR",
        f'"{INSTALL_EXE}"',
        "/RL",
        "HIGHEST",
        "/F",
    ]

    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(detail or "Windows could not register the startup task.")


# --------------------------------------------------
# Installation and first launch
# --------------------------------------------------


def confirm_installation() -> bool:
    if INSTALL_EXE.exists():
        copy_message = (
            f"An executable already exists at:\n{INSTALL_EXE}\n\n"
            "It will NOT be overwritten."
        )
    else:
        copy_message = f"The current executable will be copied to:\n{INSTALL_EXE}"

    message = (
        "Install or use the installed copy of {APP_NAME}?\n\n"
        f"{copy_message}\n\n"
        "This will also configure a visible Windows Scheduled Task "
        "named '{APP_NAME}' to start at your sign-in with the highest "
        "available privileges.\n\n"
        "Do you want to continue?"
    )

    answer = ctypes.windll.user32.MessageBoxW(
        None,
        message,
        f"{APP_NAME} Setup",
        MB_YESNO | MB_ICONQUESTION,
    )

    return answer == IDYES


def prepare_installation() -> bool:
    """
    Return True if the current process should exit because an
    installed copy has been launched.
    """
    # sys.executable points to the application EXE when frozen
    # with PyInstaller, not to the original Python interpreter.
    if not getattr(sys, "frozen", False):
        return False

    current_exe = Path(sys.executable).resolve()
    running_from_install_dir = same_path(current_exe, INSTALL_EXE)

    if not running_from_install_dir:
        if not confirm_installation():
            # Continue running this copy without installing it.
            return False

        try:
            INSTALL_DIR.mkdir(parents=True, exist_ok=True)

            # Never overwrite an existing installed executable.
            if not INSTALL_EXE.exists():
                shutil.copy2(current_exe, INSTALL_EXE)

            # Register or repair the named startup task.
            register_startup_task()

            # Start the installed copy and exit this process.
            subprocess.Popen(
                [str(INSTALL_EXE)],
                cwd=str(INSTALL_DIR),
                close_fds=True,
            )

            return True

        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            show_error(
                f"{APP_NAME} could not complete installation or startup registration.\n\n{exc}"
            )

            return False

    # The installed copy is already running. Offer to repair startup
    # registration if the task has been removed.
    if not startup_task_exists():
        answer = ctypes.windll.user32.MessageBoxW(
            None,
            "The {APP_NAME} startup task is missing.\n\nWould you like to register it again?",
            f"{APP_NAME} Startup",
            MB_YESNO | MB_ICONQUESTION,
        )

        if answer == IDYES:
            try:
                register_startup_task()
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                show_error(f"Could not register startup:\n\n{exc}")

    return False


# --------------------------------------------------
# Single-instance replacement
# --------------------------------------------------


def stop_existing_instances() -> None:
    """
    Stop all other processes named {APP_NAME}.exe before initializing
    the application.

    Use a unique executable name for this application.
    """
    current_pid = os.getpid()

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["pid"] == current_pid:
                continue

            name = (proc.info.get("name") or "").casefold()

            if name == EXE_NAME.casefold():
                proc.terminate()

                try:
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue
