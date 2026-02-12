import sys
import time
import requests
import json
import re
import os
import argparse
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PySide6.QtGui import QIcon, QClipboard, QAction
from PySide6.QtCore import QObject, QThread, Signal, Slot, QTimer

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
DEFAULT_MODEL = "gemma3:1b"
TIMEOUT_SECONDS = 120

# Force XCB on Linux to ensure clipboard access (XWayland compatibility)
if sys.platform.startswith("linux"):
    os.environ["QT_QPA_PLATFORM"] = "xcb"

# A subset of common languages for the menu.
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
}

PROMPT_TEMPLATE = """You are a professional {SOURCE_LANG} ({SOURCE_CODE}) to {TARGET_LANG} ({TARGET_CODE}) translator. Your goal is to accurately convey the meaning and nuances of the original {SOURCE_LANG} text while adhering to {TARGET_LANG} grammar, vocabulary, and cultural sensitivities.
Produce only the {TARGET_LANG} translation, without any additional explanations, notes, or commentary. Do not repeat the original text. Do not say "Here is the translation".

Please translate the following {SOURCE_LANG} text into {TARGET_LANG}:


{TEXT}"""


# -----------------------------------------------------------------------------
# Worker Thread for API Calls
# -----------------------------------------------------------------------------
class TranslatorWorker(QThread):
    finished = Signal(str, str)  # Emits (original_text, translated_text)
    error = Signal(str)

    def __init__(self, text, source_lang, target_lang, model):
        super().__init__()
        self.text = text
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.model = model

    def run(self):
        try:
            # Prepare the prompt
            source_name = self.source_lang
            source_code = LANGUAGE_MAP.get(self.source_lang, "auto")
            target_name = self.target_lang
            target_code = LANGUAGE_MAP.get(self.target_lang, "en")

            if source_code == "auto":
                source_name = "Source Language"
                source_code = "auto"

            prompt = PROMPT_TEMPLATE.format(
                SOURCE_LANG=source_name,
                SOURCE_CODE=source_code,
                TARGET_LANG=target_name,
                TARGET_CODE=target_code,
                TEXT=self.text
            )

            # Call Ollama
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                }
            }
            
            response = requests.post(OLLAMA_API_URL, json=payload, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            
            result = response.json()
            translated_text = result.get("response", "").strip()
            
            # --- Post-processing ---
            if translated_text:
                # 1. Remove common prefixes
                prefixes = [
                    r"^Here is the translation.*?:",
                    r"^Here's the translation.*?:",
                    r"^Sure, here is the translation.*?:",
                    r"^Translation:",
                    r"^Translated text:",
                ]
                for p in prefixes:
                    translated_text = re.sub(p, "", translated_text, flags=re.IGNORECASE | re.MULTILINE).strip()
                
                # 2. Smart Quote Handling
                original_has_quotes = (
                    (self.text.strip().startswith('"') and self.text.strip().endswith('"')) or 
                    (self.text.strip().startswith("'") and self.text.strip().endswith("'"))
                )

                if not original_has_quotes:
                    if translated_text.startswith('"') and translated_text.endswith('"'):
                        translated_text = translated_text[1:-1].strip()
                    elif translated_text.startswith("'") and translated_text.endswith("'"):
                        translated_text = translated_text[1:-1].strip()

                # 3. Remove Markdown code blocks if wrapped
                code_block_pattern = r"^```(?:\w+)?\s*(.*?)\s*```$"
                match = re.search(code_block_pattern, translated_text, re.DOTALL)
                if match:
                    translated_text = match.group(1).strip()

                self.finished.emit(self.text, translated_text)
            else:
                self.error.emit("Empty response from Ollama")

        except requests.exceptions.ReadTimeout:
            self.error.emit(f"Timeout after {TIMEOUT_SECONDS}s. The model took too long.")
        except Exception as e:
            self.error.emit(str(e))


# -----------------------------------------------------------------------------
# Main Application Logic
# -----------------------------------------------------------------------------
class ClipboardTranslator(QObject):
    def __init__(self, initial_model=DEFAULT_MODEL, initial_source="Auto Detect", initial_target="English"):
        super().__init__()
        self.app = QApplication.instance()
        self.clipboard = self.app.clipboard()
        
        # State
        self.is_enabled = True
        self.current_source_lang = initial_source
        self.current_target_lang = initial_target
        self.current_model = initial_model
        self.available_models = [initial_model]
        self.last_clipboard_text = ""
        self.ignore_next_change = False
        self.translator_thread = None

        # Fetch models
        self.fetch_available_models()

        # Setup System Tray
        # Try to use a standard icon if theme icon fails, but theme is best for integration
        self.tray_icon = QSystemTrayIcon(QIcon.fromTheme("edit-copy"), self.app)
        if self.tray_icon.icon().isNull():
             # Fallback: create a simple pixmap or use another standard icon
             self.tray_icon.setIcon(QIcon.fromTheme("application-x-executable"))
             
        self.tray_icon.setToolTip(f"TransPaste (Model: {self.current_model})")
        
        # Setup Menu
        self.menu = QMenu()
        self.setup_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

        # Connect Clipboard Signal
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)
        
        # Wayland Polling Fallback (1s interval)
        if sys.platform.startswith("linux"):
            self.poll_timer = QTimer(self)
            self.poll_timer.timeout.connect(self.process_clipboard)
            self.poll_timer.start(1000)

        # Notification
        self.tray_icon.showMessage(
            "TransPaste Started", 
            f"Model: {self.current_model}\nTarget: {self.current_target_lang}", 
            QSystemTrayIcon.Information, 
            3000
        )

    def setup_menu(self):
        self.menu.clear()

        # Status Action
        status_action = QAction("Status: Enabled" if self.is_enabled else "Status: Disabled", self.menu)
        status_action.setCheckable(True)
        status_action.setChecked(self.is_enabled)
        status_action.triggered.connect(self.toggle_enabled)
        self.menu.addAction(status_action)
        
        self.menu.addSeparator()

        # Source Language Menu
        source_menu = self.menu.addMenu("Source Language")
        for lang in LANGUAGE_MAP.keys():
            action = QAction(lang, self.menu)
            action.setCheckable(True)
            action.setChecked(lang == self.current_source_lang)
            action.triggered.connect(lambda checked, l=lang: self.set_source_lang(l))
            source_menu.addAction(action)

        # Target Language Menu
        target_menu = self.menu.addMenu("Target Language")
        for lang in LANGUAGE_MAP.keys():
            if lang == "Auto Detect": continue 
            action = QAction(lang, self.menu)
            action.setCheckable(True)
            action.setChecked(lang == self.current_target_lang)
            action.triggered.connect(lambda checked, l=lang: self.set_target_lang(l))
            target_menu.addAction(action)

        self.menu.addSeparator()

        # Model Selection Menu
        model_menu = self.menu.addMenu("Model")
        for model in self.available_models:
            action = QAction(model, self.menu)
            action.setCheckable(True)
            action.setChecked(model == self.current_model)
            action.triggered.connect(lambda checked, m=model: self.set_model(m))
            model_menu.addAction(action)

        # Refresh Models Action
        refresh_action = QAction("Refresh Models", self.menu)
        refresh_action.triggered.connect(self.refresh_models)
        model_menu.addSeparator()
        model_menu.addAction(refresh_action)

        self.menu.addSeparator()
        
        # Quit Action
        quit_action = QAction("Quit", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

    def toggle_enabled(self):
        self.is_enabled = not self.is_enabled
        self.setup_menu()
        msg = "Translation Enabled" if self.is_enabled else "Translation Disabled"
        self.tray_icon.showMessage("TransPaste", msg, QSystemTrayIcon.Information, 2000)

    def set_source_lang(self, lang):
        self.current_source_lang = lang
        self.setup_menu()

    def set_target_lang(self, lang):
        self.current_target_lang = lang
        self.setup_menu()

    def set_model(self, model):
        self.current_model = model
        self.setup_menu()
        self.tray_icon.setToolTip(f"TransPaste (Model: {self.current_model})")
        print(f"Model switched to: {model}")

    def fetch_available_models(self):
        try:
            response = requests.get(OLLAMA_TAGS_URL, timeout=2)
            if response.status_code == 200:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                if models:
                    self.available_models = sorted(list(set(models)))
                    if self.current_model not in self.available_models:
                         # Keep current even if not in list, or fallback
                         if DEFAULT_MODEL in self.available_models:
                             self.available_models.append(self.current_model)
                    self.available_models.sort()
        except Exception as e:
            print(f"Failed to fetch models: {e}")
    
    def refresh_models(self):
        self.fetch_available_models()
        self.setup_menu()
        self.tray_icon.showMessage("Models Refreshed", f"Found {len(self.available_models)} models.", QSystemTrayIcon.Information, 2000)

    def on_clipboard_changed(self):
        if not self.is_enabled:
            return
        QTimer.singleShot(100, self.process_clipboard)

    def process_clipboard(self):
        if self.ignore_next_change:
            self.ignore_next_change = False
            return

        text = self.clipboard.text()
        if not text or text.strip() == "":
            return

        if text == self.last_clipboard_text:
            return

        print(f"Detected copy: {text[:20]}...")
        
        if self.translator_thread and self.translator_thread.isRunning():
            try:
                self.translator_thread.finished.disconnect(self.on_translation_finished)
                self.translator_thread.error.disconnect(self.on_translation_error)
                self.translator_thread.terminate()
                self.translator_thread.wait()
            except Exception:
                pass

        self.translator_thread = TranslatorWorker(
            text, 
            self.current_source_lang, 
            self.current_target_lang, 
            self.current_model
        )
        self.translator_thread.finished.connect(self.on_translation_finished)
        self.translator_thread.error.connect(self.on_translation_error)
        self.translator_thread.start()

    def on_translation_finished(self, original_text, translated_text):
        print(f"Translation finished: {translated_text[:20]}...")
        
        self.ignore_next_change = True
        self.last_clipboard_text = translated_text
        self.clipboard.setText(translated_text)
        
        self.tray_icon.showMessage(
            "Translated", 
            f"Result copied to clipboard.\n{translated_text[:50]}...", 
            QSystemTrayIcon.Information, 
            2000
        )

    def on_translation_error(self, error_msg):
        print(f"Translation Error: {error_msg}")
        self.tray_icon.showMessage(
            "Translation Failed", 
            f"Error: {error_msg}", 
            QSystemTrayIcon.Warning, 
            3000
        )

def main():
    parser = argparse.ArgumentParser(description="TransPaste: Local LLM Clipboard Translator")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Ollama model to use (default: gemma3:1b)")
    parser.add_argument("--source", type=str, default="Auto Detect", help="Source language (default: Auto Detect)")
    parser.add_argument("--target", type=str, default="English", help="Target language (default: English)")
    
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    translator = ClipboardTranslator(
        initial_model=args.model,
        initial_source=args.source,
        initial_target=args.target
    )
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
