# Changelog

All notable changes to TransPaste will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-04-23

### Added
- Keyboard shortcut (Ctrl+Shift+T) to toggle translation on/off
- Translation history with up to 50 entries, persisted across sessions
- About dialog with version, license, and project link
- Custom prompt support - users can define their own translation prompts
- Ollama API base URL configuration via `--base-url` CLI flag
- HTTP proxy support via `--proxy` CLI flag
- Markdown code block stripping in post-processing
- Full docstrings for all classes and methods
- Type hints throughout the codebase
- ruff and black linting/formatting configuration
- pytest configuration in pyproject.toml
- GitHub Actions CI/CD workflow (test, lint, release)
- Project classifiers and keywords in pyproject.toml
- Development dependencies via `[project.optional-dependencies]`

### Changed
- Replaced `print()` based logging with Python's `logging` module
- `--debug` flag now properly controls logging verbosity (was hardcoded to True)
- Progress estimation improved from character-count heuristic to response-based tracking
- Module-level side effects removed (no more logging at import time)
- Version synchronized between `pyproject.toml` and `__init__.py`

### Fixed
- Markdown code blocks (```text ... ```) from LLM output are now properly stripped
- Version mismatch between pyproject.toml (0.2.0) and __init__.py (0.2.1)

### Removed
- Legacy duplicate files: `app.py`, `clipboard_translator.py`
- Stray files: `tmp.md`, `Thumbs.db`, `提示词参考.md`

## [0.2.0] - 2026-03-19

### Added
- Streaming translation with real-time progress updates
- Translation cancel support
- 16 languages with auto-detect support
- 7 translation styles (Default, Formal, Casual, Academic, Literary, Technical, Simple)
- 5 length control options (Unlimited, Brief, Short, Medium, Detailed)
- Temperature control (0.1, 0.3, 0.5, 0.7, 1.0)
- Dynamic model discovery from Ollama
- System tray with animated status icons
- Settings persistence via QSettings
- macOS clipboard polling fallback
- CLI arguments for model, language, style, length, temperature
- Post-processing: LLM prefix removal, smart quote handling
- Comprehensive test suite

## [0.1.0] - 2026-02-12

### Added
- Initial release
- Basic clipboard monitoring and translation
- System tray icon
- Ollama integration
