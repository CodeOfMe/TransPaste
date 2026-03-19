# AGENTS.md

Coding agent instructions for the TransPaste codebase.

## Project Overview

TransPaste is a local LLM-powered clipboard translator using Ollama. It runs as a system tray application that automatically detects clipboard text and replaces it with translations.

- **Language**: Python 3.10+
- **Framework**: PySide6 (Qt for Python)
- **License**: GPL-3.0
- **Package**: Available on PyPI as `transpaste`

---

## Build Commands

```bash
# Install in development mode
pip install -e .

# Install from PyPI
pip install transpaste

# Build package
python -m build

# Upload to PyPI (requires credentials)
twine upload dist/*

# Run the application
transpaste
# Or with options:
transpaste --model qwen3:0.6b --target French --style Formal --length Brief

# Run directly from source
python -m transpaste.main
```

## Testing

```bash
# Run all tests
python tests/test_transpaste.py

# Run specific test class
python -m pytest tests/test_transpaste.py -k TestIconGenerator -v
```

Test coverage includes:
- Icon generation for all states (idle, translating, success, error)
- Prompt building with styles and length controls
- Translation worker with mock Ollama server
- Settings persistence
- Error handling

## Linting & Formatting

```bash
# Install linting tools
pip install ruff black

# Format code
black src/transpaste/

# Lint code
ruff check src/transpaste/
```

---

## Code Style Guidelines

### Imports

Group imports in this order, separated by blank lines:

```python
# 1. Standard library
import sys
import re
import os
import argparse
from typing import Optional, Dict, Any

# 2. Third-party
import requests
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QObject, QThread, Signal, QTimer, QSettings
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Variables | `snake_case` | `current_model`, `translated_text` |
| Functions | `snake_case` | `fetch_available_models()`, `_set_source_lang()` |
| Classes | `PascalCase` | `TranslatorWorker`, `ClipboardTranslator` |
| Constants | `UPPER_SNAKE_CASE` | `OLLAMA_API_URL`, `TIMEOUT_SECONDS` |
| Private methods | `_leading_underscore` | `_on_clipboard_changed()`, `_setup_menu()` |
| Signals (Qt) | `snake_case` | `finished`, `error` |

### String Style

Use double quotes for strings. Use f-strings for formatting:

```python
message = "Translation completed"
print(f"Model switched to: {model}")
```

### Type Hints

Use type hints for function parameters and return values:

```python
def _set_source_lang(self, lang: str) -> None:
    self.current_source_lang = lang

def build_prompt(source_lang: str, target_lang: str, text: str, style: str, length: str) -> str:
    ...
```

### Error Handling

Handle specific exceptions with informative messages:

```python
try:
    response = requests.post(url, json=payload, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
except requests.exceptions.ReadTimeout:
    self.error.emit(f"Timeout after {TIMEOUT_SECONDS}s")
except requests.exceptions.ConnectionError:
    self.error.emit("Cannot connect to Ollama. Is it running?")
except Exception as e:
    self.error.emit(str(e))
```

### Qt/PySide6 Patterns

**Signals and Slots:**

```python
class TranslatorWorker(QThread):
    finished = Signal(str, str)
    error = Signal(str)

    def run(self):
        self.finished.emit(original, translated)
```

**Lambda with default argument capture:**

```python
action.triggered.connect(lambda checked, l=lang: self._set_source_lang(l))
```

**QSettings for persistence:**

```python
self.settings = QSettings("TransPaste", "TransPaste")
self.is_enabled = self.settings.value("enabled", True, type=bool)
self.settings.setValue("enabled", self.is_enabled)
```

---

## Architecture

```
TransPaste/
├── src/transpaste/
│   ├── __init__.py       # Exports main(), constants
│   └── main.py           # Core application (~550 lines)
├── app.py                # Standalone script (legacy)
├── clipboard_translator.py  # Legacy version
├── pyproject.toml
└── requirements.txt
```

**Key Components:**

1. **TranslatorWorker (QThread)**: Background thread for Ollama API calls
2. **ClipboardTranslator (QObject)**: Main logic, system tray, settings management
3. **Constants**: `LANGUAGE_MAP`, `TRANSLATION_STYLES`, `LENGTH_OPTIONS`

---

## Features

### Translation Styles

- **Default**: Standard translation
- **Formal**: Professional and polite
- **Casual**: Relaxed and friendly  
- **Academic**: Scholarly and precise
- **Literary**: Artistic and expressive
- **Technical**: Technical documentation
- **Simple**: Easy to understand

### Length Control

- **Unlimited**: No length limit
- **Brief**: ~50 words max
- **Short**: ~100 words max
- **Medium**: ~200 words max
- **Detailed**: Comprehensive translation

### Settings (Persisted)

- Show/hide notifications
- Auto copy to clipboard
- Temperature (0.1 - 1.0)
- All language/style/length preferences

---

## Dependencies

- `PySide6`: Qt bindings for GUI
- `requests`: HTTP client for Ollama API
- **External**: Ollama running on localhost:11434

---

## Platform Notes

- **Windows**: Fully supported, extra clipboard sync for reliability
- **Linux**: Requires XCB libraries; forces XWayland mode
- **macOS**: Supported

---

## After Making Changes

1. Test manually: `transpaste`
2. Verify Ollama is running with at least one model
3. Test clipboard translation with various text inputs
4. If modifying package structure: `pip install -e .`