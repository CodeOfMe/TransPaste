"""TransPaste - Local LLM Clipboard Translator.

A system tray application that automatically detects clipboard text
and replaces it with translations using Ollama's local LLMs.
"""

import argparse
import json
import logging
import math
import os
import re
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from PySide6.QtCore import QObject, QSettings, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
)

# -----------------------------------------------------------------------------
# Debug Logger
# -----------------------------------------------------------------------------
DEBUG = False

_logger = logging.getLogger("transpaste")


def setup_logging(debug: bool = False) -> None:
    """Configure logging for the application.

    Args:
        debug: If True, set log level to DEBUG with verbose output.
               If False, set log level to WARNING (errors only).
    """
    global DEBUG
    DEBUG = debug

    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )


def log(message: str, level: str = "INFO") -> None:
    """Print debug message with timestamp.

    Args:
        message: The log message.
        level: Log level string (DEBUG, INFO, WARN, ERROR).
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    _logger.log(level_map.get(level, logging.INFO), message)


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
OLLAMA_API_URL = "http://localhost:11434"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
DEFAULT_MODEL = "gemma3:1b"
TIMEOUT_SECONDS = 120

if sys.platform.startswith("linux"):
    os.environ["QT_QPA_PLATFORM"] = "xcb"

# -----------------------------------------------------------------------------
# Language Settings
# -----------------------------------------------------------------------------
LANGUAGE_MAP = {
    "Auto Detect": "auto",
    "English": "en",
    "Chinese (Simplified)": "zh-Hans",
    "Chinese (Traditional)": "zh-Hant",
    "Japanese": "ja",
    "Korean": "ko",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Russian": "ru",
    "Italian": "it",
    "Portuguese": "pt",
    "Arabic": "ar",
    "Hindi": "hi",
    "Thai": "th",
    "Vietnamese": "vi",
}

TRANSLATION_STYLES = {
    "Default": {"description": "Standard translation", "instruction": ""},
    "Formal": {
        "description": "Professional and polite",
        "instruction": "Use formal language and professional tone.",
    },
    "Casual": {"description": "Relaxed and friendly", "instruction": "Use casual, relaxed, and friendly language."},
    "Academic": {
        "description": "Scholarly and precise",
        "instruction": "Use academic language with precise terminology.",
    },
    "Literary": {"description": "Artistic and expressive", "instruction": "Use literary and artistic language."},
    "Technical": {"description": "Technical documentation", "instruction": "Use technical terminology accurately."},
    "Simple": {"description": "Easy to understand", "instruction": "Use simple and clear language."},
}

LENGTH_OPTIONS = {
    "Unlimited": {"description": "No length limit", "instruction": "", "max_words": None},
    "Brief": {"description": "~50 words max", "instruction": "Keep the translation brief.", "max_words": 50},
    "Short": {
        "description": "~100 words max",
        "instruction": "Keep the translation relatively short.",
        "max_words": 100,
    },
    "Medium": {
        "description": "~200 words max",
        "instruction": "Provide a moderate-length translation.",
        "max_words": 200,
    },
    "Detailed": {
        "description": "Detailed translation",
        "instruction": "Provide a detailed translation.",
        "max_words": None,
    },
}


# -----------------------------------------------------------------------------
# Translation History Entry
# -----------------------------------------------------------------------------
@dataclass
class TranslationEntry:
    """Represents a single translation history entry.

    Attributes:
        original: The original source text.
        translated: The translated result text.
        source_lang: Source language name.
        target_lang: Target language name.
        timestamp: ISO format timestamp of when translation occurred.
    """

    original: str
    translated: str
    source_lang: str
    target_lang: str
    timestamp: str


# -----------------------------------------------------------------------------
# Icon Generator
# -----------------------------------------------------------------------------
class IconGenerator:
    """Generates dynamic status icons for the system tray.

    Creates QPixmap-based icons for different translation states:
    idle, translating (with progress animation), success, and error.
    """

    STATUS_IDLE = "idle"
    STATUS_TRANSLATING = "translating"
    STATUS_SUCCESS = "success"
    STATUS_ERROR = "error"

    def create_icon(self, status: str = STATUS_IDLE, progress: float = 0, rotation: float = 0) -> QIcon:
        """Create an icon for the given status.

        Args:
            status: One of STATUS_IDLE, STATUS_TRANSLATING, STATUS_SUCCESS, STATUS_ERROR.
            progress: Progress value from 0.0 to 1.0 (used for translating status).
            rotation: Rotation angle in degrees (used for translating animation).

        Returns:
            QIcon object for the system tray.
        """
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        if status == self.STATUS_TRANSLATING:
            self._draw_translating_icon(painter, progress, rotation)
        elif status == self.STATUS_SUCCESS:
            self._draw_success_icon(painter)
        elif status == self.STATUS_ERROR:
            self._draw_error_icon(painter)
        else:
            self._draw_idle_icon(painter)

        painter.end()
        return QIcon(pixmap)

    def _draw_idle_icon(self, painter: QPainter) -> None:
        """Draw the idle state icon with a blue circle and 'T' letter."""
        painter.setBrush(QColor(52, 152, 219))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 56, 56)
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", 28, QFont.Bold)
        painter.setFont(font)
        painter.drawText(painter.device().rect(), Qt.AlignCenter, "T")

    def _draw_translating_icon(self, painter: QPainter, progress: float, rotation: float) -> None:
        """Draw the translating state icon with progress ring and spinning lines.

        Args:
            painter: QPainter instance.
            progress: Progress from 0.0 to 1.0.
            rotation: Rotation angle for the spinning animation.
        """
        center = 32
        radius = 26

        painter.setBrush(QColor(52, 73, 94))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 56, 56)

        if progress > 0:
            progress_angle = int(progress * 360 * 16)
            painter.setBrush(QColor(46, 204, 113))
            painter.drawPie(4, 4, 56, 56, 90 * 16, -progress_angle)

        painter.setPen(QPen(QColor(255, 255, 255), 3))
        for i in range(8):
            angle = rotation + i * 45
            rad = math.radians(angle)
            inner_r = radius - 8
            outer_r = radius - 2
            x1 = center + inner_r * math.cos(rad)
            y1 = center + inner_r * math.sin(rad)
            x2 = center + outer_r * math.cos(rad)
            y2 = center + outer_r * math.sin(rad)
            alpha = int(255 * (1 - i / 8))
            painter.setPen(QPen(QColor(255, 255, 255, alpha), 3))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        if progress > 0:
            painter.setPen(QColor(255, 255, 255))
            font = QFont("Arial", 12, QFont.Bold)
            painter.setFont(font)
            percent = int(progress * 100)
            painter.drawText(painter.device().rect(), Qt.AlignCenter, f"{percent}%")

    def _draw_success_icon(self, painter: QPainter) -> None:
        """Draw the success state icon with a green circle and checkmark."""
        painter.setBrush(QColor(46, 204, 113))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 56, 56)
        painter.setPen(QPen(QColor(255, 255, 255), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(20, 32, 28, 40)
        painter.drawLine(28, 40, 44, 24)

    def _draw_error_icon(self, painter: QPainter) -> None:
        """Draw the error state icon with a red circle and X mark."""
        painter.setBrush(QColor(231, 76, 60))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 56, 56)
        painter.setPen(QPen(QColor(255, 255, 255), 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(22, 22, 42, 42)
        painter.drawLine(42, 22, 22, 42)


# -----------------------------------------------------------------------------
# Prompt Builder
# -----------------------------------------------------------------------------
def build_prompt(
    source_lang: str, source_code: str, target_lang: str, target_code: str, text: str, style: str, length: str
) -> str:
    """Build the translation prompt for Ollama.

    Args:
        source_lang: Source language display name.
        source_code: Source language code (e.g., 'en', 'auto').
        target_lang: Target language display name.
        target_code: Target language code (e.g., 'zh-Hans').
        text: The text to translate.
        style: Translation style name (e.g., 'Formal', 'Casual').
        length: Length control name (e.g., 'Brief', 'Unlimited').

    Returns:
        Complete prompt string for the LLM.
    """
    style_info = TRANSLATION_STYLES.get(style, TRANSLATION_STYLES["Default"])
    length_info = LENGTH_OPTIONS.get(length, LENGTH_OPTIONS["Unlimited"])

    if source_code == "auto":
        display_source = "Source Language"
    else:
        display_source = source_lang

    base_prompt = (
        f"You are a professional {display_source} ({source_code}) to "
        f"{target_lang} ({target_code}) translator.\n\n"
        f"CRITICAL RULES:\n"
        f"1. Produce ONLY the {target_lang} translation\n"
        f"2. Do NOT include any explanations or commentary\n"
        f"3. Start directly with the translated text"
    )

    if style_info["instruction"]:
        base_prompt += f"\n\nSTYLE: {style_info['instruction']}"

    if length_info["instruction"]:
        base_prompt += f"\n\nLENGTH: {length_info['instruction']}"

    base_prompt += f"\n\nTranslate:\n\n{text}"
    return base_prompt


# -----------------------------------------------------------------------------
# Translator Worker
# -----------------------------------------------------------------------------
class TranslatorWorker(QThread):
    """Background thread that handles translation via Ollama API.

    Signals:
        finished: Emitted when translation completes (original_text, translated_text).
        error: Emitted when an error occurs (error_message).
        progress: Emitted during translation (progress_0_to_1, status_message).
    """

    finished = Signal(str, str)
    error = Signal(str)
    progress = Signal(float, str)

    def __init__(self, text: str, config: Dict[str, Any]):
        """Initialize the translator worker.

        Args:
            text: The text to translate.
            config: Dictionary containing translation configuration
                    (source_lang, target_lang, model, style, length, temperature, base_url).
        """
        super().__init__()
        self.text = text
        self.config = config
        self._is_cancelled = False
        log(f"TranslatorWorker created with text length: {len(text)}")

    def cancel(self) -> None:
        """Cancel the ongoing translation."""
        self._is_cancelled = True
        log("Translation cancelled", "WARN")

    def run(self) -> None:
        """Execute the translation process in a background thread."""
        log("TranslatorWorker started")
        try:
            source_name = self.config["source_lang"]
            source_code = LANGUAGE_MAP.get(source_name, "auto")
            target_name = self.config["target_lang"]
            target_code = LANGUAGE_MAP.get(target_name, "en")

            if source_code == "auto":
                source_name = "Source Language"

            prompt = build_prompt(
                source_name,
                source_code,
                target_name,
                target_code,
                self.text,
                self.config.get("style", "Default"),
                self.config.get("length", "Unlimited"),
            )
            log(f"Prompt built, length: {len(prompt)} chars")

            payload = {
                "model": self.config["model"],
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": self.config.get("temperature", 0.3)},
            }

            base_url = self.config.get("base_url", OLLAMA_API_URL).rstrip("/")
            api_url = f"{base_url}/api/generate"
            log(f"Connecting to Ollama at {api_url}...")
            self.progress.emit(0.05, "Connecting to Ollama...")

            proxies = self.config.get("proxies")
            response = requests.post(
                api_url,
                json=payload,
                stream=True,
                timeout=TIMEOUT_SECONDS,
                proxies=proxies,
            )
            response.raise_for_status()
            log("Connected to Ollama successfully")

            translated_text = ""
            total_chars = 0
            estimated_chars = max(len(self.text) * 1.5, 20)

            self.progress.emit(0.1, "Translating...")

            for line in response.iter_lines():
                if self._is_cancelled:
                    log("Translation cancelled by user")
                    return

                if line:
                    try:
                        data = json.loads(line.decode("utf-8"))
                        if "response" in data:
                            translated_text += data["response"]
                            total_chars += len(data["response"])

                            progress = min(0.1 + (total_chars / estimated_chars) * 0.85, 0.95)
                            preview = translated_text[-30:] if len(translated_text) > 30 else translated_text
                            self.progress.emit(progress, f"Translating: {preview}...")

                        if data.get("done", False):
                            log(f"Ollama signaled done, total chars: {total_chars}")
                            break
                    except json.JSONDecodeError:
                        continue

            translated_text = translated_text.strip()
            log(f"Raw translation length: {len(translated_text)}")

            if translated_text:
                self.progress.emit(0.98, "Processing result...")
                translated_text = self._post_process(translated_text)
                self.progress.emit(1.0, "Done!")
                log(f"Translation complete: {translated_text[:50]}...")
                self.finished.emit(self.text, translated_text)
            else:
                log("Empty response from Ollama", "ERROR")
                self.error.emit("Empty response from Ollama")

        except requests.exceptions.ReadTimeout:
            log(f"Timeout after {TIMEOUT_SECONDS}s", "ERROR")
            self.error.emit(f"Timeout after {TIMEOUT_SECONDS}s")
        except requests.exceptions.ConnectionError as e:
            log(f"Connection error: {e}", "ERROR")
            self.error.emit("Cannot connect to Ollama. Is it running?")
        except requests.exceptions.HTTPError as e:
            log(f"HTTP error: {e}", "ERROR")
            self.error.emit(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            log(f"Unexpected error: {e}", "ERROR")
            log(traceback.format_exc(), "ERROR")
            self.error.emit(str(e))

    def _post_process(self, translated_text: str) -> str:
        """Clean up the raw translation output.

        Removes common LLM prefixes, markdown code blocks, and handles
        smart quote preservation.

        Args:
            translated_text: Raw text from Ollama.

        Returns:
            Cleaned translation text.
        """
        prefixes = [
            r"^Here is the translation.*?:",
            r"^Here's the translation.*?:",
            r"^Sure, here is the translation.*?:",
            r"^Translation:",
            r"^Translated text:",
        ]
        for p in prefixes:
            translated_text = re.sub(p, "", translated_text, flags=re.IGNORECASE).strip()

        markdown_pattern = r"^```(?:text|markdown)?\s*\n?(.*?)\n?```$"
        translated_text = re.sub(markdown_pattern, r"\1", translated_text, flags=re.DOTALL).strip()

        original_has_quotes = (self.text.strip().startswith('"') and self.text.strip().endswith('"')) or (
            self.text.strip().startswith("'") and self.text.strip().endswith("'")
        )

        if not original_has_quotes:
            if translated_text.startswith('"') and translated_text.endswith('"'):
                translated_text = translated_text[1:-1].strip()
            elif translated_text.startswith("'") and translated_text.endswith("'"):
                translated_text = translated_text[1:-1].strip()

        return translated_text


# -----------------------------------------------------------------------------
# About Dialog
# -----------------------------------------------------------------------------
class AboutDialog(QDialog):
    """About dialog showing version, license, and project links."""

    def __init__(self, parent=None):
        """Initialize the about dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("About TransPaste")
        self.setFixedSize(350, 220)

        layout = QVBoxLayout(self)

        from transpaste import __version__

        title_label = QLabel(f"<h2>TransPaste v{__version__}</h2>")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        desc_label = QLabel(
            "Local LLM Clipboard Translator\n"
            "Powered by Ollama\n\n"
            "Licensed under GPL-3.0\n"
            "https://github.com/CodeOfMe/TransPaste"
        )
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


# -----------------------------------------------------------------------------
# Main Application
# -----------------------------------------------------------------------------
class ClipboardTranslator(QObject):
    """Main application class managing clipboard translation.

    Handles system tray UI, clipboard monitoring, translation workflow,
    settings persistence, and translation history.
    """

    MAX_HISTORY = 50

    def __init__(
        self,
        initial_model: str = DEFAULT_MODEL,
        initial_source: str = "Auto Detect",
        initial_target: str = "English",
        base_url: str = OLLAMA_API_URL,
        proxies: Optional[Dict[str, str]] = None,
    ):
        """Initialize the clipboard translator.

        Args:
            initial_model: Ollama model to use.
            initial_source: Source language name.
            initial_target: Target language name.
            base_url: Ollama API base URL.
            proxies: HTTP proxy configuration dict.
        """
        super().__init__()

        log("=" * 50)
        log("Initializing ClipboardTranslator")
        log("=" * 50)

        self.app = QApplication.instance()
        log(f"QApplication instance: {self.app}")

        self.clipboard = self.app.clipboard()
        log(f"Clipboard object: {self.clipboard}")

        self.settings = QSettings("TransPaste", "TransPaste")
        self.icon_generator = IconGenerator()

        self.base_url = base_url
        self.proxies = proxies

        self._load_settings(initial_model, initial_source, initial_target)
        self._load_history()

        self.last_clipboard_text = ""
        self.ignore_next_change = False
        self.translator_thread = None
        self.translation_count = 0
        self.current_progress = 0.0
        self.rotation_angle = 0
        self.clipboard_change_count = 0

        self.translation_history: List[TranslationEntry] = []

        log("Fetching available models...")
        self.fetch_available_models()

        log("Setting up tray icon...")
        self._setup_tray_icon()

        log("Setting up clipboard monitor...")
        self._setup_clipboard_monitor()

        log("Setting up animation timer...")
        self._setup_animation_timer()

        log("Setting up keyboard shortcuts...")
        self._setup_shortcuts()

        log("Showing startup notification...")
        self._show_startup_notification()

        log("ClipboardTranslator initialized successfully!")

    def _load_history(self) -> None:
        """Load translation history from settings."""
        try:
            history_json = self.settings.value("translation_history", "")
            if history_json:
                history_data = json.loads(history_json)
                self.translation_history = [TranslationEntry(**entry) for entry in history_data[-self.MAX_HISTORY :]]
                log(f"Loaded {len(self.translation_history)} history entries")
        except Exception as e:
            log(f"Failed to load history: {e}", "WARN")
            self.translation_history = []

    def _save_history(self) -> None:
        """Save translation history to settings."""
        try:
            history_data = [
                {
                    "original": e.original,
                    "translated": e.translated,
                    "source_lang": e.source_lang,
                    "target_lang": e.target_lang,
                    "timestamp": e.timestamp,
                }
                for e in self.translation_history[-self.MAX_HISTORY :]
            ]
            self.settings.setValue("translation_history", json.dumps(history_data))
        except Exception as e:
            log(f"Failed to save history: {e}", "WARN")

    def _add_to_history(self, original: str, translated: str) -> None:
        """Add a translation to history.

        Args:
            original: Original source text.
            translated: Translated result text.
        """
        entry = TranslationEntry(
            original=original,
            translated=translated,
            source_lang=self.current_source_lang,
            target_lang=self.current_target_lang,
            timestamp=datetime.now().isoformat(),
        )
        self.translation_history.append(entry)
        if len(self.translation_history) > self.MAX_HISTORY:
            self.translation_history = self.translation_history[-self.MAX_HISTORY :]
        self._save_history()

    def _load_settings(self, default_model: str, default_source: str, default_target: str) -> None:
        """Load persisted settings from QSettings.

        Args:
            default_model: Default model if not previously set.
            default_source: Default source language if not previously set.
            default_target: Default target language if not previously set.
        """
        self.is_enabled = self.settings.value("enabled", True, type=bool)
        self.current_source_lang = self.settings.value("source_lang", default_source)
        self.current_target_lang = self.settings.value("target_lang", default_target)
        self.current_model = self.settings.value("model", default_model)
        self.current_style = self.settings.value("style", "Default")
        self.current_length = self.settings.value("length", "Unlimited")
        self.temperature = self.settings.value("temperature", 0.3, type=float)
        self.show_notifications = self.settings.value("show_notifications", True, type=bool)
        self.auto_copy = self.settings.value("auto_copy", True, type=bool)
        self.custom_prompt = self.settings.value("custom_prompt", "")
        self.available_models = [self.current_model]

        log(f"Settings loaded: enabled={self.is_enabled}, model={self.current_model}")
        log(f"  source={self.current_source_lang}, target={self.current_target_lang}")

    def _save_settings(self) -> None:
        """Persist current settings to QSettings."""
        self.settings.setValue("enabled", self.is_enabled)
        self.settings.setValue("source_lang", self.current_source_lang)
        self.settings.setValue("target_lang", self.current_target_lang)
        self.settings.setValue("model", self.current_model)
        self.settings.setValue("style", self.current_style)
        self.settings.setValue("length", self.current_length)
        self.settings.setValue("temperature", self.temperature)
        self.settings.setValue("show_notifications", self.show_notifications)
        self.settings.setValue("auto_copy", self.auto_copy)
        self.settings.setValue("custom_prompt", self.custom_prompt)
        log("Settings saved")

    def _setup_tray_icon(self) -> None:
        """Create and show the system tray icon with context menu."""
        icon = self.icon_generator.create_icon(IconGenerator.STATUS_IDLE)
        self.tray_icon = QSystemTrayIcon(icon, self.app)

        self._update_tooltip()

        self.menu = QMenu()
        self.setup_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

        log(f"Tray icon created and shown: {self.tray_icon.isVisible()}")

    def _setup_animation_timer(self) -> None:
        """Start the animation timer for translating icon."""
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.start(80)
        log("Animation timer started")

    def _setup_shortcuts(self) -> None:
        """Set up global keyboard shortcuts."""
        self.toggle_shortcut = QShortcut(QKeySequence("Ctrl+Shift+T"), self.app)
        self.toggle_shortcut.activated.connect(self._toggle_enabled)
        log("Keyboard shortcut registered: Ctrl+Shift+T")

    def _update_animation(self) -> None:
        """Update the translating icon animation frame."""
        if self.translator_thread and self.translator_thread.isRunning():
            self.rotation_angle = (self.rotation_angle + 15) % 360
            icon = self.icon_generator.create_icon(
                IconGenerator.STATUS_TRANSLATING, self.current_progress, self.rotation_angle
            )
            self.tray_icon.setIcon(icon)

    def _update_tooltip(self) -> None:
        """Update the system tray tooltip with current status."""
        status = "ON" if self.is_enabled else "OFF"
        if self.translator_thread and self.translator_thread.isRunning():
            self.tray_icon.setToolTip(f"TransPaste - Translating... {int(self.current_progress * 100)}%")
        else:
            self.tray_icon.setToolTip(f"TransPaste [{status}] - {self.current_model}")

    def _setup_clipboard_monitor(self) -> None:
        """Connect clipboard change signal and set up macOS polling fallback."""
        log("Connecting clipboard.dataChanged signal...")
        result = self.clipboard.dataChanged.connect(self._on_clipboard_changed)
        log(f"Signal connected: {result}")

        if sys.platform == "darwin":
            log("macOS detected, starting polling timer as backup...")
            self.poll_timer = QTimer(self)
            self.poll_timer.timeout.connect(self._poll_clipboard)
            self.poll_timer.start(500)

            current_text = self.clipboard.text()
            log(f"Current clipboard text on startup: '{current_text[:50]}...' (len={len(current_text)})")

    def _poll_clipboard(self) -> None:
        """Fallback polling for macOS clipboard detection."""
        if not self.is_enabled:
            return

        text = self.clipboard.text()
        if text and text.strip() and text != self.last_clipboard_text:
            log(f"[POLL] Detected clipboard change: '{text[:30]}...'")
            self._process_text(text)

    def _show_startup_notification(self) -> None:
        """Show notification on application startup."""
        if self.show_notifications:
            self.tray_icon.showMessage(
                "TransPaste Started",
                f"Model: {self.current_model}\nCopy text to translate",
                QSystemTrayIcon.Information,
                2000,
            )

    def setup_menu(self) -> None:
        """Build the system tray context menu."""
        self.menu.clear()
        self._add_status_action()
        self.menu.addSeparator()
        self._add_language_menus()
        self.menu.addSeparator()
        self._add_style_menu()
        self._add_length_menu()
        self.menu.addSeparator()
        self._add_model_menu()
        self.menu.addSeparator()
        self._add_settings_menu()
        self.menu.addSeparator()
        self._add_history_menu()
        self.menu.addSeparator()
        self._add_stats_action()
        self.menu.addSeparator()
        self._add_about_action()
        self.menu.addSeparator()
        self._add_quit_action()

    def _add_status_action(self) -> None:
        """Add the enable/disable toggle action to the menu."""
        status_text = "Status: ON" if self.is_enabled else "Status: OFF"
        status_action = QAction(status_text, self.menu)
        status_action.setCheckable(True)
        status_action.setChecked(self.is_enabled)
        status_action.setShortcut("Ctrl+Shift+T")
        status_action.triggered.connect(self._toggle_enabled)
        self.menu.addAction(status_action)

    def _add_language_menus(self) -> None:
        """Add source and target language submenus."""
        source_menu = self.menu.addMenu("Source Language")
        for lang in LANGUAGE_MAP.keys():
            action = QAction(lang, self.menu)
            action.setCheckable(True)
            action.setChecked(lang == self.current_source_lang)
            action.triggered.connect(lambda checked, lang=lang: self._set_source_lang(lang))
            source_menu.addAction(action)

        target_menu = self.menu.addMenu("Target Language")
        for lang in LANGUAGE_MAP.keys():
            if lang == "Auto Detect":
                continue
            action = QAction(lang, self.menu)
            action.setCheckable(True)
            action.setChecked(lang == self.current_target_lang)
            action.triggered.connect(lambda checked, lang=lang: self._set_target_lang(lang))
            target_menu.addAction(action)

    def _add_style_menu(self) -> None:
        """Add translation style submenu."""
        style_menu = self.menu.addMenu("Translation Style")
        for style_name, style_info in TRANSLATION_STYLES.items():
            action = QAction(f"{style_name} - {style_info['description']}", self.menu)
            action.setCheckable(True)
            action.setChecked(style_name == self.current_style)
            action.triggered.connect(lambda checked, s=style_name: self._set_style(s))
            style_menu.addAction(action)

    def _add_length_menu(self) -> None:
        """Add length control submenu."""
        length_menu = self.menu.addMenu("Length Control")
        for length_name, length_info in LENGTH_OPTIONS.items():
            action = QAction(f"{length_name} - {length_info['description']}", self.menu)
            action.setCheckable(True)
            action.setChecked(length_name == self.current_length)
            action.triggered.connect(lambda checked, length_opt=length_name: self._set_length(length_opt))
            length_menu.addAction(action)

    def _add_model_menu(self) -> None:
        """Add model selection submenu with refresh option."""
        model_menu = self.menu.addMenu("Model")
        for model in self.available_models:
            action = QAction(model, self.menu)
            action.setCheckable(True)
            action.setChecked(model == self.current_model)
            action.triggered.connect(lambda checked, m=model: self._set_model(m))
            model_menu.addAction(action)

        refresh_action = QAction("Refresh Models", self.menu)
        refresh_action.triggered.connect(self._refresh_models)
        model_menu.addSeparator()
        model_menu.addAction(refresh_action)

    def _add_settings_menu(self) -> None:
        """Add settings submenu with notifications, auto-copy, temperature, and custom prompt."""
        settings_menu = self.menu.addMenu("Settings")

        notifications_action = QAction("Show Notifications", self.menu)
        notifications_action.setCheckable(True)
        notifications_action.setChecked(self.show_notifications)
        notifications_action.triggered.connect(self._toggle_notifications)
        settings_menu.addAction(notifications_action)

        auto_copy_action = QAction("Auto Copy to Clipboard", self.menu)
        auto_copy_action.setCheckable(True)
        auto_copy_action.setChecked(self.auto_copy)
        auto_copy_action.triggered.connect(self._toggle_auto_copy)
        settings_menu.addAction(auto_copy_action)

        settings_menu.addSeparator()

        temp_menu = settings_menu.addMenu("Temperature")
        for temp in [0.1, 0.3, 0.5, 0.7, 1.0]:
            action = QAction(f"{temp}", self.menu)
            action.setCheckable(True)
            action.setChecked(abs(self.temperature - temp) < 0.01)
            action.triggered.connect(lambda checked, t=temp: self._set_temperature(t))
            temp_menu.addAction(action)

        settings_menu.addSeparator()

        prompt_action = QAction("Custom Prompt...", self.menu)
        prompt_action.triggered.connect(self._set_custom_prompt)
        settings_menu.addAction(prompt_action)

        if self.custom_prompt:
            clear_prompt = QAction("Clear Custom Prompt", self.menu)
            clear_prompt.triggered.connect(self._clear_custom_prompt)
            settings_menu.addAction(clear_prompt)

    def _add_history_menu(self) -> None:
        """Add translation history submenu."""
        history_menu = self.menu.addMenu("Translation History")

        if not self.translation_history:
            empty_action = QAction("No history yet", self.menu)
            empty_action.setEnabled(False)
            history_menu.addAction(empty_action)
            return

        recent = self.translation_history[-10:]
        for entry in reversed(recent):
            preview = entry.original[:30] + "..." if len(entry.original) > 30 else entry.original
            action = QAction(f"{preview}", self.menu)
            action.setToolTip(f"{entry.original}\n\n{entry.translated}")
            action.triggered.connect(lambda checked, e=entry: self._show_history_entry(e))
            history_menu.addAction(action)

        if len(self.translation_history) > 10:
            history_menu.addSeparator()
            show_all = QAction(f"Show all ({len(self.translation_history)} entries)...", self.menu)
            show_all.triggered.connect(self._show_full_history)
            history_menu.addAction(show_all)

        history_menu.addSeparator()
        clear_action = QAction("Clear History", self.menu)
        clear_action.triggered.connect(self._clear_history)
        history_menu.addAction(clear_action)

    def _show_history_entry(self, entry: TranslationEntry) -> None:
        """Show a dialog with a single history entry.

        Args:
            entry: The translation history entry to display.
        """
        dialog = QDialog(self.app.activeWindow())
        dialog.setWindowTitle("Translation History")
        dialog.setFixedSize(500, 300)

        layout = QVBoxLayout(dialog)

        original_label = QLabel(f"<b>Original ({entry.source_lang}):</b>")
        layout.addWidget(original_label)

        original_text = QLabel(entry.original)
        original_text.setWordWrap(True)
        layout.addWidget(original_text)

        translated_label = QLabel(f"<b>Translated ({entry.target_lang}):</b>")
        layout.addWidget(translated_label)

        translated_text = QLabel(entry.translated)
        translated_text.setWordWrap(True)
        layout.addWidget(translated_text)

        time_label = QLabel(f"<small>{entry.timestamp}</small>")
        layout.addWidget(time_label)

        copy_btn = QPushButton("Copy Translation")
        copy_btn.clicked.connect(lambda: self._copy_to_clipboard(entry.translated))
        layout.addWidget(copy_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _show_full_history(self) -> None:
        """Show a dialog with the full translation history."""
        dialog = QDialog(self.app.activeWindow())
        dialog.setWindowTitle("Full Translation History")
        dialog.setFixedSize(600, 500)

        layout = QVBoxLayout(dialog)

        history_text = ""
        for entry in reversed(self.translation_history):
            history_text += f"[{entry.timestamp}] {entry.source_lang} -> {entry.target_lang}\n"
            history_text += f"  Original: {entry.original[:80]}\n"
            history_text += f"  Translation: {entry.translated[:80]}\n\n"

        text_label = QLabel(history_text.strip())
        text_label.setWordWrap(True)
        from PySide6.QtWidgets import QScrollArea

        scroll = QScrollArea()
        scroll.setWidget(text_label)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _clear_history(self) -> None:
        """Clear all translation history."""
        self.translation_history = []
        self._save_history()
        log("Translation history cleared")

    def _add_stats_action(self) -> None:
        """Add the translation count stats action."""
        stats_action = QAction(f"Translations: {self.translation_count}", self.menu)
        stats_action.setEnabled(False)
        self.menu.addAction(stats_action)

    def _add_about_action(self) -> None:
        """Add the About dialog action."""
        about_action = QAction("About TransPaste", self.menu)
        about_action.triggered.connect(self._show_about)
        self.menu.addAction(about_action)

    def _add_quit_action(self) -> None:
        """Add the quit action."""
        quit_action = QAction("Quit", self.menu)
        quit_action.triggered.connect(self._quit_app)
        self.menu.addAction(quit_action)

    def _toggle_enabled(self) -> None:
        """Toggle translation enabled/disabled state."""
        self.is_enabled = not self.is_enabled
        self._save_settings()
        self._update_tooltip()
        self.setup_menu()
        icon = self.icon_generator.create_icon(IconGenerator.STATUS_IDLE)
        self.tray_icon.setIcon(icon)
        log(f"Enabled toggled to: {self.is_enabled}")

    def _set_source_lang(self, lang: str) -> None:
        """Set the source language.

        Args:
            lang: Language name from LANGUAGE_MAP keys.
        """
        self.current_source_lang = lang
        self._save_settings()
        self.setup_menu()
        log(f"Source language set to: {lang}")

    def _set_target_lang(self, lang: str) -> None:
        """Set the target language.

        Args:
            lang: Language name from LANGUAGE_MAP keys.
        """
        self.current_target_lang = lang
        self._save_settings()
        self.setup_menu()
        log(f"Target language set to: {lang}")

    def _set_style(self, style: str) -> None:
        """Set the translation style.

        Args:
            style: Style name from TRANSLATION_STYLES keys.
        """
        self.current_style = style
        self._save_settings()
        self.setup_menu()
        log(f"Style set to: {style}")

    def _set_length(self, length: str) -> None:
        """Set the length control option.

        Args:
            length: Length name from LENGTH_OPTIONS keys.
        """
        self.current_length = length
        self._save_settings()
        self.setup_menu()
        log(f"Length set to: {length}")

    def _set_model(self, model: str) -> None:
        """Set the Ollama model to use.

        Args:
            model: Model name (e.g., 'gemma3:1b').
        """
        self.current_model = model
        self._save_settings()
        self._update_tooltip()
        self.setup_menu()
        log(f"Model set to: {model}")

    def _set_temperature(self, temp: float) -> None:
        """Set the model temperature.

        Args:
            temp: Temperature value (0.1 to 1.0).
        """
        self.temperature = temp
        self._save_settings()
        self.setup_menu()
        log(f"Temperature set to: {temp}")

    def _set_custom_prompt(self) -> None:
        """Show dialog to set a custom translation prompt."""
        from PySide6.QtWidgets import QDialogButtonBox, QTextEdit

        dialog = QDialog(self.app.activeWindow())
        dialog.setWindowTitle("Custom Prompt")
        dialog.setFixedSize(500, 400)

        layout = QVBoxLayout(dialog)

        info_label = QLabel(
            "Enter a custom prompt template. Use {source_lang}, {target_lang}, "
            "and {text} as placeholders.\nLeave empty to use the default prompt."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        text_edit = QTextEdit()
        text_edit.setPlainText(self.custom_prompt)
        layout.addWidget(text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            self.custom_prompt = text_edit.toPlainText().strip()
            self._save_settings()
            log(f"Custom prompt set: {bool(self.custom_prompt)}")

    def _clear_custom_prompt(self) -> None:
        """Clear the custom prompt and revert to default."""
        self.custom_prompt = ""
        self._save_settings()
        self.setup_menu()
        log("Custom prompt cleared")

    def _toggle_notifications(self) -> None:
        """Toggle system notification display."""
        self.show_notifications = not self.show_notifications
        self._save_settings()
        self.setup_menu()

    def _toggle_auto_copy(self) -> None:
        """Toggle auto-copy to clipboard after translation."""
        self.auto_copy = not self.auto_copy
        self._save_settings()
        self.setup_menu()

    def fetch_available_models(self) -> None:
        """Fetch available models from Ollama and update the model list."""
        try:
            proxies = self.proxies
            response = requests.get(OLLAMA_TAGS_URL, timeout=2, proxies=proxies)
            if response.status_code == 200:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                if models:
                    self.available_models = sorted(list(set(models)))
                    log(f"Available models: {self.available_models}")
                    if self.current_model not in self.available_models:
                        self.available_models.append(self.current_model)
                    self.available_models.sort()
        except Exception as e:
            log(f"Failed to fetch models: {e}", "WARN")

    def _refresh_models(self) -> None:
        """Refresh the available models list and rebuild menu."""
        self.fetch_available_models()
        self.setup_menu()

    def _on_clipboard_changed(self) -> None:
        """Handle clipboard data change signal."""
        self.clipboard_change_count += 1
        log(f"[SIGNAL] Clipboard changed (count: {self.clipboard_change_count})")

        if not self.is_enabled:
            log("Translation is disabled, ignoring")
            return

        QTimer.singleShot(100, self._get_clipboard_text)

    def _get_clipboard_text(self) -> None:
        """Read text from clipboard and process it."""
        log("Getting clipboard text...")
        text = self.clipboard.text()
        log(f"Clipboard text: '{text[:50]}...' (len={len(text)})")
        self._process_text(text)

    def _process_text(self, text: str) -> None:
        """Validate and start translation for clipboard text.

        Args:
            text: The clipboard text to potentially translate.
        """
        log(f"Processing text: '{text[:50]}...' (len={len(text)})")

        if self.ignore_next_change:
            self.ignore_next_change = False
            log("Ignoring this change (was set by ourselves)")
            return

        if not text or text.strip() == "":
            log("Empty or whitespace text, ignoring")
            return

        if text == self.last_clipboard_text:
            log("Same as last clipboard text, ignoring")
            return

        if self.translator_thread and self.translator_thread.isRunning():
            log("Translation already in progress, skipping")
            return

        log(f"Starting translation for: '{text[:50]}...'")
        self._start_translation(text)

    def _start_translation(self, text: str) -> None:
        """Start translation of the given text.

        Args:
            text: The text to translate.
        """
        if self.translator_thread and self.translator_thread.isRunning():
            self.translator_thread.cancel()
            self.translator_thread.wait(1000)

        self.current_progress = 0.0
        icon = self.icon_generator.create_icon(IconGenerator.STATUS_TRANSLATING, 0, 0)
        self.tray_icon.setIcon(icon)
        self._update_tooltip()

        config = {
            "source_lang": self.current_source_lang,
            "target_lang": self.current_target_lang,
            "model": self.current_model,
            "style": self.current_style,
            "length": self.current_length,
            "temperature": self.temperature,
            "base_url": self.base_url,
            "proxies": self.proxies,
            "custom_prompt": self.custom_prompt,
        }

        self.translator_thread = TranslatorWorker(text, config)
        self.translator_thread.finished.connect(self._on_translation_finished)
        self.translator_thread.error.connect(self._on_translation_error)
        self.translator_thread.progress.connect(self._on_translation_progress)
        self.translator_thread.start()
        log("Translation thread started")

    def _on_translation_progress(self, progress: float, message: str) -> None:
        """Handle translation progress update.

        Args:
            progress: Progress value from 0.0 to 1.0.
            message: Status message describing current progress.
        """
        self.current_progress = progress
        self._update_tooltip()
        log(f"Progress: {int(progress * 100)}% - {message}")

    def _on_translation_finished(self, original_text: str, translated_text: str) -> None:
        """Handle successful translation completion.

        Args:
            original_text: The original source text.
            translated_text: The translated result.
        """
        log("Translation finished!")
        log(f"  Original: '{original_text[:50]}...'")
        log(f"  Translated: '{translated_text[:50]}...'")

        icon = self.icon_generator.create_icon(IconGenerator.STATUS_SUCCESS)
        self.tray_icon.setIcon(icon)

        self.translation_count += 1
        self.setup_menu()

        self._add_to_history(original_text, translated_text)

        if self.auto_copy:
            self._copy_to_clipboard(translated_text)

        QTimer.singleShot(1500, self._reset_to_idle)

        if self.show_notifications:
            preview = translated_text[:50] + "..." if len(translated_text) > 50 else translated_text
            self.tray_icon.showMessage("Translation Complete", preview, QSystemTrayIcon.Information, 2000)

    def _reset_to_idle(self) -> None:
        """Reset the tray icon to idle state if no translation is running."""
        if not (self.translator_thread and self.translator_thread.isRunning()):
            icon = self.icon_generator.create_icon(IconGenerator.STATUS_IDLE)
            self.tray_icon.setIcon(icon)
            self._update_tooltip()

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard while preventing re-trigger.

        Args:
            text: The text to copy.
        """
        self.ignore_next_change = True
        self.last_clipboard_text = text

        log(f"Copying to clipboard: '{text[:50]}...'")
        self.clipboard.setText(text)

        if sys.platform == "darwin":
            log("macOS: doing extra clipboard sync")
            QTimer.singleShot(50, lambda: self.clipboard.setText(text))
            QTimer.singleShot(150, lambda: self.clipboard.setText(text))

        log("Text copied to clipboard")

    def _on_translation_error(self, error_msg: str) -> None:
        """Handle translation error.

        Args:
            error_msg: Error message describing what went wrong.
        """
        log(f"Translation error: {error_msg}", "ERROR")

        icon = self.icon_generator.create_icon(IconGenerator.STATUS_ERROR)
        self.tray_icon.setIcon(icon)

        QTimer.singleShot(2000, self._reset_to_idle)

        if self.show_notifications:
            self.tray_icon.showMessage("Translation Failed", error_msg, QSystemTrayIcon.Warning, 3000)

    def _show_about(self) -> None:
        """Show the About dialog."""
        dialog = AboutDialog(self.app.activeWindow())
        dialog.exec()

    def _quit_app(self) -> None:
        """Quit the application, saving all settings."""
        log("Quitting application...")
        if self.translator_thread and self.translator_thread.isRunning():
            self.translator_thread.cancel()
            self.translator_thread.wait(2000)
        self._save_settings()
        self._save_history()
        self.app.quit()


def main() -> None:
    """Entry point for the TransPaste application."""
    parser = argparse.ArgumentParser(description="TransPaste: Local LLM Clipboard Translator")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Ollama model to use")
    parser.add_argument("--source", type=str, default="Auto Detect", help="Source language")
    parser.add_argument("--target", type=str, default="English", help="Target language")
    parser.add_argument("--style", type=str, default="Default", help="Translation style")
    parser.add_argument("--length", type=str, default="Unlimited", help="Length control")
    parser.add_argument("--temperature", type=float, default=0.3, help="Model temperature")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--base-url", type=str, default=OLLAMA_API_URL, help="Ollama API base URL")
    parser.add_argument("--proxy", type=str, default=None, help="HTTP proxy URL (e.g., http://127.0.0.1:7890)")

    args = parser.parse_args()

    setup_logging(debug=args.debug)

    log(f"Platform: {sys.platform}")
    log(f"Python version: {sys.version}")
    log(f"OLLAMA_API_URL: {args.base_url}")

    proxies = None
    if args.proxy:
        proxies = {"http": args.proxy, "https": args.proxy}
        log(f"Using proxy: {args.proxy}")

    log("Creating QApplication...")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    log("Creating ClipboardTranslator...")
    ClipboardTranslator(
        initial_model=args.model,
        initial_source=args.source,
        initial_target=args.target,
        base_url=args.base_url,
        proxies=proxies,
    )

    log("Starting event loop...")
    log("Copy some text to clipboard to test!")
    print()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
