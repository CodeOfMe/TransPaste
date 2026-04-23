#!/usr/bin/env python3
"""
TransPaste Comprehensive Test Suite
Tests all components and scenarios
"""

import sys
import os
import json
import time
import threading
import unittest
import socket
from unittest.mock import Mock, patch, MagicMock
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QIcon, QPixmap

# Import directly from transpaste.main module
import importlib.util
spec = importlib.util.spec_from_file_location(
    "transpaste_main",
    os.path.join(os.path.dirname(__file__), '..', 'src', 'transpaste', 'main.py')
)
transpaste_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transpaste_main)

IconGenerator = transpaste_main.IconGenerator
TranslatorWorker = transpaste_main.TranslatorWorker
ClipboardTranslator = transpaste_main.ClipboardTranslator
AboutDialog = transpaste_main.AboutDialog
TranslationEntry = transpaste_main.TranslationEntry
LANGUAGE_MAP = transpaste_main.LANGUAGE_MAP
TRANSLATION_STYLES = transpaste_main.TRANSLATION_STYLES
LENGTH_OPTIONS = transpaste_main.LENGTH_OPTIONS
build_prompt = transpaste_main.build_prompt


def find_free_port():
    """Find a free port for testing"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


TEST_PORT = find_free_port()


class MockOllamaHandler(BaseHTTPRequestHandler):
    """Mock Ollama API server for testing"""

    response_text = "This is a test translation."
    should_fail = False
    delay = 0.0

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/api/tags":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {
                "models": [
                    {"name": "test-model:latest"},
                    {"name": "gemma3:1b"}
                ]
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if MockOllamaHandler.should_fail:
            self.send_response(500)
            self.end_headers()
            return

        if self.path == "/api/generate":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode()
            data = json.loads(body)

            if data.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()

                translation = MockOllamaHandler.response_text
                for i, char in enumerate(translation):
                    time.sleep(MockOllamaHandler.delay)
                    chunk = json.dumps({"response": char, "done": False}) + "\n"
                    self.wfile.write(chunk.encode())
                    self.wfile.flush()

                final = json.dumps({"response": "", "done": True}) + "\n"
                self.wfile.write(final.encode())
                self.wfile.flush()
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response = {"response": MockOllamaHandler.response_text}
                self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()


class TestIconGenerator(unittest.TestCase):
    """Test icon generation for different states"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.generator = IconGenerator()

    def test_idle_icon(self):
        """Test idle state icon generation"""
        icon = self.generator.create_icon(IconGenerator.STATUS_IDLE)
        self.assertIsNotNone(icon)
        self.assertFalse(icon.isNull())

    def test_translating_icon(self):
        """Test translating state icon with progress"""
        for progress in [0, 0.25, 0.5, 0.75, 1.0]:
            icon = self.generator.create_icon(
                IconGenerator.STATUS_TRANSLATING,
                progress=progress,
                rotation=0
            )
            self.assertIsNotNone(icon)
            self.assertFalse(icon.isNull())

    def test_success_icon(self):
        """Test success state icon"""
        icon = self.generator.create_icon(IconGenerator.STATUS_SUCCESS)
        self.assertIsNotNone(icon)
        self.assertFalse(icon.isNull())

    def test_error_icon(self):
        """Test error state icon"""
        icon = self.generator.create_icon(IconGenerator.STATUS_ERROR)
        self.assertIsNotNone(icon)
        self.assertFalse(icon.isNull())

    def test_rotation_animation(self):
        """Test rotation animation generates different icons"""
        icons = []
        for rotation in range(0, 360, 45):
            icon = self.generator.create_icon(
                IconGenerator.STATUS_TRANSLATING,
                progress=0.5,
                rotation=rotation
            )
            icons.append(icon)
        self.assertEqual(len(icons), 8)


class TestPromptBuilder(unittest.TestCase):
    """Test prompt building logic"""

    def test_basic_prompt(self):
        """Test basic prompt generation"""
        prompt = build_prompt(
            "English", "en",
            "Chinese (Simplified)", "zh-Hans",
            "Hello world",
            "Default", "Unlimited"
        )
        self.assertIn("English", prompt)
        self.assertIn("Chinese (Simplified)", prompt)
        self.assertIn("Hello world", prompt)

    def test_style_in_prompt(self):
        """Test style instructions are included"""
        prompt = build_prompt(
            "English", "en",
            "French", "fr",
            "Hello",
            "Formal", "Unlimited"
        )
        self.assertIn("formal", prompt.lower())

    def test_length_in_prompt(self):
        """Test length instructions are included"""
        prompt = build_prompt(
            "English", "en",
            "Spanish", "es",
            "Hello",
            "Default", "Brief"
        )
        self.assertIn("brief", prompt.lower())

    def test_auto_detect_source(self):
        """Test auto-detect source language handling"""
        prompt = build_prompt(
            "Auto Detect", "auto",
            "English", "en",
            "你好",
            "Default", "Unlimited"
        )
        self.assertIn("Source Language", prompt)

    def test_unknown_style_defaults(self):
        """Test unknown style falls back to Default"""
        prompt = build_prompt(
            "English", "en", "French", "fr",
            "Test", "NonExistent", "Unlimited"
        )
        self.assertIsNotNone(prompt)

    def test_unknown_length_defaults(self):
        """Test unknown length falls back to Unlimited"""
        prompt = build_prompt(
            "English", "en", "French", "fr",
            "Test", "Default", "NonExistent"
        )
        self.assertIsNotNone(prompt)


class TestTranslatorWorker(unittest.TestCase):
    """Test translation worker thread"""

    server = None
    server_thread = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.server = HTTPServer(('localhost', TEST_PORT), MockOllamaHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.shutdown()

    def setUp(self):
        self.config = {
            "source_lang": "English",
            "target_lang": "Chinese (Simplified)",
            "model": "test-model:latest",
            "style": "Default",
            "length": "Unlimited",
            "temperature": 0.3
        }
        MockOllamaHandler.response_text = "这是测试翻译"
        MockOllamaHandler.should_fail = False
        MockOllamaHandler.delay = 0.0

    def test_successful_translation(self):
        """Test successful translation"""
        original_url = transpaste_main.OLLAMA_API_URL
        transpaste_main.OLLAMA_API_URL = f"http://localhost:{TEST_PORT}"

        try:
            config = {**self.config, "base_url": f"http://localhost:{TEST_PORT}"}
            worker = TranslatorWorker("Hello world", config)

            result = {"finished": None, "error": None}

            def on_finished(original, translated):
                result["finished"] = (original, translated)

            def on_error(msg):
                result["error"] = msg

            worker.finished.connect(on_finished)
            worker.error.connect(on_error)
            worker.run()

            self.assertIsNone(result["error"])
            self.assertIsNotNone(result["finished"])
            self.assertEqual(result["finished"][0], "Hello world")
        finally:
            transpaste_main.OLLAMA_API_URL = original_url

    def test_progress_signals(self):
        """Test progress signals are emitted"""
        original_url = transpaste_main.OLLAMA_API_URL
        transpaste_main.OLLAMA_API_URL = f"http://localhost:{TEST_PORT}"

        try:
            config = {**self.config, "base_url": f"http://localhost:{TEST_PORT}"}
            worker = TranslatorWorker("Test", config)

            progress_values = []

            def on_progress(value, msg):
                progress_values.append(value)

            worker.progress.connect(on_progress)
            worker.run()

            self.assertTrue(len(progress_values) > 0)
            self.assertTrue(all(0 <= p <= 1 for p in progress_values))
        finally:
            transpaste_main.OLLAMA_API_URL = original_url

    def test_server_error(self):
        """Test server error handling"""
        original_url = transpaste_main.OLLAMA_API_URL
        transpaste_main.OLLAMA_API_URL = f"http://localhost:{TEST_PORT}"

        try:
            MockOllamaHandler.should_fail = True

            config = {**self.config, "base_url": f"http://localhost:{TEST_PORT}"}
            worker = TranslatorWorker("Test", config)

            error_msg = None

            def on_error(msg):
                nonlocal error_msg
                error_msg = msg

            worker.error.connect(on_error)
            worker.run()

            self.assertIsNotNone(error_msg)
        finally:
            MockOllamaHandler.should_fail = False
            transpaste_main.OLLAMA_API_URL = original_url

    def test_post_process_removes_prefixes(self):
        """Test post-processing removes common prefixes"""
        test_cases = [
            ("Here is the translation: Hello", "Hello"),
            ("Translation: World", "World"),
            ("Sure, here is the translation: Test", "Test"),
        ]

        for input_text, expected in test_cases:
            worker = TranslatorWorker("original", self.config)
            result = worker._post_process(input_text)
            self.assertEqual(result, expected)

    def test_post_process_handles_quotes(self):
        """Test smart quote handling"""
        worker = TranslatorWorker('"quoted text"', self.config)
        result = worker._post_process('"translated"')
        self.assertEqual(result, '"translated"')

        worker = TranslatorWorker('unquoted text', self.config)
        result = worker._post_process('"translated"')
        self.assertEqual(result, 'translated')

    def test_post_process_removes_markdown_blocks(self):
        """Test post-processing removes markdown code blocks"""
        test_cases = [
            ("```text\nHello World\n```", "Hello World"),
            ("```markdown\nTest translation\n```", "Test translation"),
            ("```\nSimple translation\n```", "Simple translation"),
        ]

        for input_text, expected in test_cases:
            worker = TranslatorWorker("original", self.config)
            result = worker._post_process(input_text)
            self.assertEqual(result, expected)

    def test_custom_base_url(self):
        """Test custom base URL is used"""
        config = {**self.config, "base_url": f"http://localhost:{TEST_PORT}"}
        worker = TranslatorWorker("Test", config)

        result = {"finished": None, "error": None}

        def on_finished(original, translated):
            result["finished"] = (original, translated)

        def on_error(msg):
            result["error"] = msg

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.run()

        self.assertIsNone(result["error"])
        self.assertIsNotNone(result["finished"])


class TestConstants(unittest.TestCase):
    """Test defined constants"""

    def test_language_map_valid(self):
        """Test language map has valid entries"""
        self.assertIn("Auto Detect", LANGUAGE_MAP)
        self.assertIn("English", LANGUAGE_MAP)
        self.assertIn("Chinese (Simplified)", LANGUAGE_MAP)

        for lang, code in LANGUAGE_MAP.items():
            self.assertIsInstance(lang, str)
            self.assertIsInstance(code, str)

    def test_translation_styles_valid(self):
        """Test translation styles have valid structure"""
        for name, info in TRANSLATION_STYLES.items():
            self.assertIn("description", info)
            self.assertIn("instruction", info)
            self.assertIsInstance(info["description"], str)
            self.assertIsInstance(info["instruction"], str)

    def test_length_options_valid(self):
        """Test length options have valid structure"""
        for name, info in LENGTH_OPTIONS.items():
            self.assertIn("description", info)
            self.assertIn("instruction", info)
            self.assertIn("max_words", info)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error scenarios"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_very_long_text(self):
        """Test very long text handling"""
        long_text = "Hello " * 10000
        prompt = build_prompt(
            "English", "en", "Chinese (Simplified)", "zh-Hans",
            long_text, "Default", "Unlimited"
        )
        self.assertIn(long_text, prompt)

    def test_special_characters(self):
        """Test special characters handling"""
        special_texts = [
            "Hello\nWorld",
            "Tab\there",
            "Quote: \"test\"",
            "Unicode: 中文日本語한국어",
        ]

        for text in special_texts:
            prompt = build_prompt(
                "English", "en", "Chinese", "zh",
                text, "Default", "Unlimited"
            )
            self.assertIn(text, prompt)

    def test_all_styles(self):
        """Test all translation styles"""
        for style_name in TRANSLATION_STYLES.keys():
            prompt = build_prompt(
                "English", "en", "French", "fr",
                "Test", style_name, "Unlimited"
            )
            self.assertIsNotNone(prompt)

    def test_all_lengths(self):
        """Test all length options"""
        for length_name in LENGTH_OPTIONS.keys():
            prompt = build_prompt(
                "English", "en", "French", "fr",
                "Test", "Default", length_name
            )
            self.assertIsNotNone(prompt)

    def test_connection_error_handling(self):
        """Test connection error when Ollama is not running"""
        config = {
            "source_lang": "English",
            "target_lang": "Chinese (Simplified)",
            "model": "test-model",
            "style": "Default",
            "length": "Unlimited",
            "temperature": 0.3,
            "base_url": "http://localhost:19999",
        }
        worker = TranslatorWorker("Test", config)

        error_msg = None

        def on_error(msg):
            nonlocal error_msg
            error_msg = msg

        worker.error.connect(on_error)
        worker.run()

        self.assertIsNotNone(error_msg)
        self.assertIn("Cannot connect to Ollama", error_msg)


class TestTranslationEntry(unittest.TestCase):
    """Test translation history entry dataclass"""

    def test_entry_creation(self):
        """Test creating a translation entry"""
        entry = TranslationEntry(
            original="Hello",
            translated="你好",
            source_lang="English",
            target_lang="Chinese (Simplified)",
            timestamp="2026-04-23T10:00:00",
        )
        self.assertEqual(entry.original, "Hello")
        self.assertEqual(entry.translated, "你好")
        self.assertEqual(entry.source_lang, "English")
        self.assertEqual(entry.target_lang, "Chinese (Simplified)")


class TestSetupLogging(unittest.TestCase):
    """Test logging setup"""

    def test_debug_mode(self):
        """Test debug logging setup"""
        transpaste_main.setup_logging(debug=True)
        self.assertTrue(transpaste_main.DEBUG)

    def test_normal_mode(self):
        """Test normal logging setup"""
        transpaste_main.setup_logging(debug=False)
        self.assertFalse(transpaste_main.DEBUG)


def run_tests():
    """Run all tests with detailed output"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestIconGenerator,
        TestPromptBuilder,
        TestTranslatorWorker,
        TestConstants,
        TestEdgeCases,
        TestTranslationEntry,
        TestSetupLogging,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")

    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"  - {test}")

    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"  - {test}")

    if result.wasSuccessful():
        print("\nAll tests passed!")
        return 0
    else:
        print("\nSome tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
