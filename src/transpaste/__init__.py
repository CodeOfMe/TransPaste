"""TransPaste - Local LLM Clipboard Translator."""

from .main import (
    LANGUAGE_MAP,
    LENGTH_OPTIONS,
    TRANSLATION_STYLES,
    AboutDialog,
    ClipboardTranslator,
    IconGenerator,
    TranslationEntry,
    TranslatorWorker,
    build_prompt,
    main,
    setup_logging,
)

__version__ = "0.3.5"

__all__ = [
    "main",
    "build_prompt",
    "IconGenerator",
    "TranslatorWorker",
    "ClipboardTranslator",
    "AboutDialog",
    "TranslationEntry",
    "LANGUAGE_MAP",
    "TRANSLATION_STYLES",
    "LENGTH_OPTIONS",
    "setup_logging",
]
