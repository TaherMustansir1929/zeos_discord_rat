# Zeos Discord RAT v2

> Install deps
```python
uv sync
```

> Install pyinstaller as dev dep
```python
uv add --dev pyinstaller
```

> Generate exe file
```python
uv run pyinstaller --onefile --noconsole --paths src --name "<your-app-name>" main.py
```

```python
uv run pyinstaller --onefile --name "installer" installer.py
```