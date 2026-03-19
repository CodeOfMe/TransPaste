import sys
import re
import os
import argparse
import json
import math
import traceback
from datetime import datetime
from typing import Optional, Dict, Any

import requests
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont, QPen
from PySide6.QtCore import QObject, QThread, Signal, QTimer, QSettings, Qt

# -----------------------------------------------------------------------------
# Debug Logger
# -----------------------------------------------------------------------------
DEBUG = True

def log(message: str, level: str = "INFO"):
    """Print debug message with timestamp"""
    if DEBUG:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] {message}")

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
DEFAULT_MODEL = "gemma3:1b"
TIMEOUT_SECONDS = 120

if sys.platform.startswith("linux"):
    os.environ["QT_QPA_PLATFORM"] = "xcb"

log(f"Platform: {sys.platform}")
log(f"Python version: {sys.version}")
log(f"OLLAMA_API_URL: {OLLAMA_API_URL}")

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
    "Formal": {"description": "Professional and polite", "instruction": "Use formal language, professional tone, and polite expressions."},
    "Casual": {"description": "Relaxed and friendly", "instruction": "Use casual, relaxed, and friendly language."},
    "Academic": {"description": "Scholarly and precise", "instruction": "Use academic language with precise terminology."},
    "Literary": {"description": "Artistic and expressive", "instruction": "Use literary and artistic language."},
    "Technical": {"description": "Technical documentation", "instruction": "Use technical terminology accurately."},
    "Simple": {"description": "Easy to understand", "instruction": "Use simple and clear language."},
}

LENGTH_OPTIONS = {
    "Unlimited": {"description": "No length limit", "instruction": "", "max_words": None},
    "Brief": {"description": "~50 words max", "instruction": "Keep the translation brief.", "max_words": 50},
    "Short": {"description": "~100 words max", "instruction": "Keep the translation relatively short.", "max_words": 100},
    "Medium": {"description": "~200 words max", "instruction": "Provide a moderate-length translation.", "max_words": 200},
    "Detailed": {"description": "Detailed translation", "instruction": "Provide a detailed translation.", "max_words": None},
}


# -----------------------------------------------------------------------------
# Icon Generator
# -----------------------------------------------------------------------------
class IconGenerator:
    STATUS_IDLE = "idle"
    STATUS_TRANSLATING = "translating"
    STATUS_SUCCESS = "success"
    STATUS_ERROR = "error"

    def create_icon(self, status: str = STATUS_IDLE, progress: float = 0, rotation: float = 0) -> QIcon:
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

    def _draw_idle_icon(self, painter: QPainter):
        painter.setBrush(QColor(52, 152, 219))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 56, 56)
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", 28, QFont.Bold)
        painter.setFont(font)
        painter.drawText(painter.device().rect(), Qt.AlignCenter, "T")

    def _draw_translating_icon(self, painter: QPainter, progress: float, rotation: float):
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

    def _draw_success_icon(self, painter: QPainter):
        painter.setBrush(QColor(46, 204, 113))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 56, 56)
        painter.setPen(QPen(QColor(255, 255, 255), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(20, 32, 28, 40)
        painter.drawLine(28, 40, 44, 24)

    def _draw_error_icon(self, painter: QPainter):
        painter.setBrush(QColor(231, 76, 60))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 56, 56)
        painter.setPen(QPen(QColor(255, 255, 255), 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(22, 22, 42, 42)
        painter.drawLine(42, 22, 22, 42)


# -----------------------------------------------------------------------------
# Prompt Builder
# -----------------------------------------------------------------------------
def build_prompt(source_lang: str, source_code: str, target_lang: str,
                 target_code: str, text: str, style: str, length: str) -> str:
    style_info = TRANSLATION_STYLES.get(style, TRANSLATION_STYLES["Default"])
    length_info = LENGTH_OPTIONS.get(length, LENGTH_OPTIONS["Unlimited"])

    if source_code == "auto":
        display_source = "Source Language"
    else:
        display_source = source_lang

    base_prompt = f"""You are a professional {display_source} ({source_code}) to {target_lang} ({target_code}) translator.

CRITICAL RULES:
1. Produce ONLY the {target_lang} translation
2. Do NOT include any explanations or commentary
3. Start directly with the translated text"""

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
    finished = Signal(str, str)
    error = Signal(str)
    progress = Signal(float, str)

    def __init__(self, text: str, config: Dict[str, Any]):
        super().__init__()
        self.text = text
        self.config = config
        self._is_cancelled = False
        log(f"TranslatorWorker created with text length: {len(text)}")

    def cancel(self):
        self._is_cancelled = True
        log("Translation cancelled", "WARN")

    def run(self):
        log("TranslatorWorker started")
        try:
            source_name = self.config["source_lang"]
            source_code = LANGUAGE_MAP.get(source_name, "auto")
            target_name = self.config["target_lang"]
            target_code = LANGUAGE_MAP.get(target_name, "en")

            if source_code == "auto":
                source_name = "Source Language"

            prompt = build_prompt(
                source_name, source_code,
                target_name, target_code,
                self.text,
                self.config.get("style", "Default"),
                self.config.get("length", "Unlimited")
            )
            log(f"Prompt built, length: {len(prompt)} chars")

            payload = {
                "model": self.config["model"],
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": self.config.get("temperature", 0.3)}
            }

            log(f"Connecting to Ollama at {OLLAMA_API_URL}...")
            self.progress.emit(0.05, "Connecting to Ollama...")

            response = requests.post(
                OLLAMA_API_URL,
                json=payload,
                stream=True,
                timeout=TIMEOUT_SECONDS
            )
            response.raise_for_status()
            log("Connected to Ollama successfully")

            translated_text = ""
            total_tokens = 0
            estimated_total = max(len(self.text) // 2, 10)

            self.progress.emit(0.1, "Translating...")

            for line in response.iter_lines():
                if self._is_cancelled:
                    log("Translation cancelled by user")
                    return

                if line:
                    try:
                        data = json.loads(line.decode('utf-8'))
                        if 'response' in data:
                            translated_text += data['response']
                            total_tokens += 1

                            progress = min(0.1 + (total_tokens / estimated_total) * 0.85, 0.95)
                            preview = translated_text[-30:] if len(translated_text) > 30 else translated_text
                            self.progress.emit(progress, f"Translating: {preview}...")

                        if data.get('done', False):
                            log(f"Ollama signaled done, total tokens: {total_tokens}")
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
        prefixes = [
            r"^Here is the translation.*?:",
            r"^Here's the translation.*?:",
            r"^Sure, here is the translation.*?:",
            r"^Translation:",
            r"^Translated text:",
        ]
        for p in prefixes:
            translated_text = re.sub(p, "", translated_text, flags=re.IGNORECASE).strip()

        original_has_quotes = (
            (self.text.strip().startswith('"') and self.text.strip().endswith('"')) or
            (self.text.strip().startswith("'") and self.text.strip().endswith("'"))
        )

        if not original_has_quotes:
            if translated_text.startswith('"') and translated_text.endswith('"'):
                translated_text = translated_text[1:-1].strip()
            elif translated_text.startswith("'") and translated_text.endswith("'"):
                translated_text = translated_text[1:-1].strip()

        return translated_text


# -----------------------------------------------------------------------------
# Main Application
# -----------------------------------------------------------------------------
class ClipboardTranslator(QObject):
    def __init__(self, initial_model: str = DEFAULT_MODEL,
                 initial_source: str = "Auto Detect",
                 initial_target: str = "English"):
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

        self._load_settings(initial_model, initial_source, initial_target)

        self.last_clipboard_text = ""
        self.ignore_next_change = False
        self.translator_thread = None
        self.translation_count = 0
        self.current_progress = 0.0
        self.rotation_angle = 0
        self.clipboard_change_count = 0

        log("Fetching available models...")
        self.fetch_available_models()
        
        log("Setting up tray icon...")
        self._setup_tray_icon()
        
        log("Setting up clipboard monitor...")
        self._setup_clipboard_monitor()
        
        log("Setting up animation timer...")
        self._setup_animation_timer()

        log("Showing startup notification...")
        self._show_startup_notification()
        
        log("ClipboardTranslator initialized successfully!")

    def _load_settings(self, default_model: str, default_source: str, default_target: str):
        self.is_enabled = self.settings.value("enabled", True, type=bool)
        self.current_source_lang = self.settings.value("source_lang", default_source)
        self.current_target_lang = self.settings.value("target_lang", default_target)
        self.current_model = self.settings.value("model", default_model)
        self.current_style = self.settings.value("style", "Default")
        self.current_length = self.settings.value("length", "Unlimited")
        self.temperature = self.settings.value("temperature", 0.3, type=float)
        self.show_notifications = self.settings.value("show_notifications", True, type=bool)
        self.auto_copy = self.settings.value("auto_copy", True, type=bool)
        self.available_models = [self.current_model]
        
        log(f"Settings loaded: enabled={self.is_enabled}, model={self.current_model}")
        log(f"  source={self.current_source_lang}, target={self.current_target_lang}")

    def _save_settings(self):
        self.settings.setValue("enabled", self.is_enabled)
        self.settings.setValue("source_lang", self.current_source_lang)
        self.settings.setValue("target_lang", self.current_target_lang)
        self.settings.setValue("model", self.current_model)
        self.settings.setValue("style", self.current_style)
        self.settings.setValue("length", self.current_length)
        self.settings.setValue("temperature", self.temperature)
        self.settings.setValue("show_notifications", self.show_notifications)
        self.settings.setValue("auto_copy", self.auto_copy)
        log("Settings saved")

    def _setup_tray_icon(self):
        icon = self.icon_generator.create_icon(IconGenerator.STATUS_IDLE)
        self.tray_icon = QSystemTrayIcon(icon, self.app)
        
        self._update_tooltip()
        
        self.menu = QMenu()
        self.setup_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()
        
        log(f"Tray icon created and shown: {self.tray_icon.isVisible()}")

    def _setup_animation_timer(self):
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.start(80)
        log("Animation timer started")

    def _update_animation(self):
        if self.translator_thread and self.translator_thread.isRunning():
            self.rotation_angle = (self.rotation_angle + 15) % 360
            icon = self.icon_generator.create_icon(
                IconGenerator.STATUS_TRANSLATING,
                self.current_progress,
                self.rotation_angle
            )
            self.tray_icon.setIcon(icon)

    def _update_tooltip(self):
        status = "ON" if self.is_enabled else "OFF"
        if self.translator_thread and self.translator_thread.isRunning():
            self.tray_icon.setToolTip(f"TransPaste - Translating... {int(self.current_progress * 100)}%")
        else:
            self.tray_icon.setToolTip(f"TransPaste [{status}] - {self.current_model}")

    def _setup_clipboard_monitor(self):
        log("Connecting clipboard.dataChanged signal...")
        result = self.clipboard.dataChanged.connect(self._on_clipboard_changed)
        log(f"Signal connected: {result}")
        
        # macOS may need polling fallback
        if sys.platform == "darwin":
            log("macOS detected, starting polling timer as backup...")
            self.poll_timer = QTimer(self)
            self.poll_timer.timeout.connect(self._poll_clipboard)
            self.poll_timer.start(500)
            
            # Also try to check current clipboard
            current_text = self.clipboard.text()
            log(f"Current clipboard text on startup: '{current_text[:50]}...' (len={len(current_text)})")

    def _poll_clipboard(self):
        """Fallback polling for macOS"""
        if not self.is_enabled:
            return
            
        text = self.clipboard.text()
        if text and text.strip() and text != self.last_clipboard_text:
            log(f"[POLL] Detected clipboard change: '{text[:30]}...'")
            self._process_text(text)

    def _show_startup_notification(self):
        if self.show_notifications:
            self.tray_icon.showMessage(
                "TransPaste Started",
                f"Model: {self.current_model}\nCopy text to translate",
                QSystemTrayIcon.Information,
                2000
            )

    def setup_menu(self):
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
        self._add_stats_action()
        self.menu.addSeparator()
        self._add_quit_action()

    def _add_status_action(self):
        status_text = "Status: ON" if self.is_enabled else "Status: OFF"
        status_action = QAction(status_text, self.menu)
        status_action.setCheckable(True)
        status_action.setChecked(self.is_enabled)
        status_action.triggered.connect(self._toggle_enabled)
        self.menu.addAction(status_action)

    def _add_language_menus(self):
        source_menu = self.menu.addMenu("Source Language")
        for lang in LANGUAGE_MAP.keys():
            action = QAction(lang, self.menu)
            action.setCheckable(True)
            action.setChecked(lang == self.current_source_lang)
            action.triggered.connect(lambda checked, l=lang: self._set_source_lang(l))
            source_menu.addAction(action)

        target_menu = self.menu.addMenu("Target Language")
        for lang in LANGUAGE_MAP.keys():
            if lang == "Auto Detect":
                continue
            action = QAction(lang, self.menu)
            action.setCheckable(True)
            action.setChecked(lang == self.current_target_lang)
            action.triggered.connect(lambda checked, l=lang: self._set_target_lang(l))
            target_menu.addAction(action)

    def _add_style_menu(self):
        style_menu = self.menu.addMenu("Translation Style")
        for style_name, style_info in TRANSLATION_STYLES.items():
            action = QAction(f"{style_name} - {style_info['description']}", self.menu)
            action.setCheckable(True)
            action.setChecked(style_name == self.current_style)
            action.triggered.connect(lambda checked, s=style_name: self._set_style(s))
            style_menu.addAction(action)

    def _add_length_menu(self):
        length_menu = self.menu.addMenu("Length Control")
        for length_name, length_info in LENGTH_OPTIONS.items():
            action = QAction(f"{length_name} - {length_info['description']}", self.menu)
            action.setCheckable(True)
            action.setChecked(length_name == self.current_length)
            action.triggered.connect(lambda checked, l=length_name: self._set_length(l))
            length_menu.addAction(action)

    def _add_model_menu(self):
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

    def _add_settings_menu(self):
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

    def _add_stats_action(self):
        stats_action = QAction(f"Translations: {self.translation_count}", self.menu)
        stats_action.setEnabled(False)
        self.menu.addAction(stats_action)

    def _add_quit_action(self):
        quit_action = QAction("Quit", self.menu)
        quit_action.triggered.connect(self._quit_app)
        self.menu.addAction(quit_action)

    def _toggle_enabled(self):
        self.is_enabled = not self.is_enabled
        self._save_settings()
        self._update_tooltip()
        self.setup_menu()
        icon = self.icon_generator.create_icon(IconGenerator.STATUS_IDLE)
        self.tray_icon.setIcon(icon)
        log(f"Enabled toggled to: {self.is_enabled}")

    def _set_source_lang(self, lang: str):
        self.current_source_lang = lang
        self._save_settings()
        self.setup_menu()
        log(f"Source language set to: {lang}")

    def _set_target_lang(self, lang: str):
        self.current_target_lang = lang
        self._save_settings()
        self.setup_menu()
        log(f"Target language set to: {lang}")

    def _set_style(self, style: str):
        self.current_style = style
        self._save_settings()
        self.setup_menu()
        log(f"Style set to: {style}")

    def _set_length(self, length: str):
        self.current_length = length
        self._save_settings()
        self.setup_menu()
        log(f"Length set to: {length}")

    def _set_model(self, model: str):
        self.current_model = model
        self._save_settings()
        self._update_tooltip()
        self.setup_menu()
        log(f"Model set to: {model}")

    def _set_temperature(self, temp: float):
        self.temperature = temp
        self._save_settings()
        self.setup_menu()
        log(f"Temperature set to: {temp}")

    def _toggle_notifications(self):
        self.show_notifications = not self.show_notifications
        self._save_settings()
        self.setup_menu()

    def _toggle_auto_copy(self):
        self.auto_copy = not self.auto_copy
        self._save_settings()
        self.setup_menu()

    def fetch_available_models(self):
        try:
            log(f"Fetching models from {OLLAMA_TAGS_URL}...")
            response = requests.get(OLLAMA_TAGS_URL, timeout=2)
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

    def _refresh_models(self):
        self.fetch_available_models()
        self.setup_menu()

    def _on_clipboard_changed(self):
        """Called when clipboard data changes (signal)"""
        self.clipboard_change_count += 1
        log(f"[SIGNAL] Clipboard changed (count: {self.clipboard_change_count})")
        
        if not self.is_enabled:
            log("Translation is disabled, ignoring")
            return
            
        QTimer.singleShot(100, self._get_clipboard_text)

    def _get_clipboard_text(self):
        """Actually get clipboard text"""
        log("Getting clipboard text...")
        text = self.clipboard.text()
        log(f"Clipboard text: '{text[:50]}...' (len={len(text)})")
        self._process_text(text)

    def _process_text(self, text: str):
        """Process clipboard text and start translation"""
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

    def _start_translation(self, text: str):
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
        }

        self.translator_thread = TranslatorWorker(text, config)
        self.translator_thread.finished.connect(self._on_translation_finished)
        self.translator_thread.error.connect(self._on_translation_error)
        self.translator_thread.progress.connect(self._on_translation_progress)
        self.translator_thread.start()
        log("Translation thread started")

    def _on_translation_progress(self, progress: float, message: str):
        self.current_progress = progress
        self._update_tooltip()
        log(f"Progress: {int(progress * 100)}% - {message}")

    def _on_translation_finished(self, original_text: str, translated_text: str):
        log(f"Translation finished!")
        log(f"  Original: '{original_text[:50]}...'")
        log(f"  Translated: '{translated_text[:50]}...'")

        icon = self.icon_generator.create_icon(IconGenerator.STATUS_SUCCESS)
        self.tray_icon.setIcon(icon)

        self.translation_count += 1
        self.setup_menu()

        if self.auto_copy:
            self._copy_to_clipboard(translated_text)

        QTimer.singleShot(1500, self._reset_to_idle)

        if self.show_notifications:
            preview = translated_text[:50] + "..." if len(translated_text) > 50 else translated_text
            self.tray_icon.showMessage("Translation Complete", preview, QSystemTrayIcon.Information, 2000)

    def _reset_to_idle(self):
        if not (self.translator_thread and self.translator_thread.isRunning()):
            icon = self.icon_generator.create_icon(IconGenerator.STATUS_IDLE)
            self.tray_icon.setIcon(icon)
            self._update_tooltip()

    def _copy_to_clipboard(self, text: str):
        self.ignore_next_change = True
        self.last_clipboard_text = text
        
        log(f"Copying to clipboard: '{text[:50]}...'")
        self.clipboard.setText(text)

        if sys.platform == "darwin":
            log("macOS: doing extra clipboard sync")
            QTimer.singleShot(50, lambda: self.clipboard.setText(text))
            QTimer.singleShot(150, lambda: self.clipboard.setText(text))

        log("Text copied to clipboard")

    def _on_translation_error(self, error_msg: str):
        log(f"Translation error: {error_msg}", "ERROR")

        icon = self.icon_generator.create_icon(IconGenerator.STATUS_ERROR)
        self.tray_icon.setIcon(icon)

        QTimer.singleShot(2000, self._reset_to_idle)

        if self.show_notifications:
            self.tray_icon.showMessage("Translation Failed", error_msg, QSystemTrayIcon.Warning, 3000)

    def _quit_app(self):
        log("Quitting application...")
        if self.translator_thread and self.translator_thread.isRunning():
            self.translator_thread.cancel()
            self.translator_thread.wait(2000)
        self._save_settings()
        self.app.quit()


def main():
    print("\n" + "=" * 60)
    print("TransPaste - Local LLM Clipboard Translator")
    print("=" * 60 + "\n")
    
    parser = argparse.ArgumentParser(description="TransPaste: Local LLM Clipboard Translator")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Ollama model to use")
    parser.add_argument("--source", type=str, default="Auto Detect", help="Source language")
    parser.add_argument("--target", type=str, default="English", help="Target language")
    parser.add_argument("--style", type=str, default="Default", help="Translation style")
    parser.add_argument("--length", type=str, default="Unlimited", help="Length control")
    parser.add_argument("--temperature", type=float, default=0.3, help="Model temperature")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()

    global DEBUG
    DEBUG = True  # Always enable debug for now

    log("Creating QApplication...")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    log("Creating ClipboardTranslator...")
    translator = ClipboardTranslator(
        initial_model=args.model,
        initial_source=args.source,
        initial_target=args.target
    )
    
    log("Starting event loop...")
    log("Copy some text to clipboard to test!")
    print()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()