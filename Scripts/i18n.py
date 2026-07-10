import json
import os
import sys
import locale

LOCALE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locale")

LANGUAGES = {
    "en_US": "English",
    "zh_CN": "简体中文",
}

class Translator:
    def __init__(self, language="en_US"):
        self.language = language
        self.translations = {}
        self._load()

    def _load(self):
        file_path = os.path.join(LOCALE_DIR, f"{self.language}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.translations = json.load(f)
            except Exception:
                self.translations = {}

    def tr(self, text, **kwargs):
        translated = self.translations.get(text, text)
        if kwargs:
            try:
                return translated.format(**kwargs)
            except KeyError:
                return text.format(**kwargs)
        return translated


_current = Translator()

def _(text, **kwargs):
    return _current.tr(text, **kwargs)

def set_language(lang):
    global _current
    _current = Translator(lang)

def get_language():
    return _current.language

def get_available_languages():
    return dict(LANGUAGES)

def detect_system_language():
    try:
        sys_lang, _ = locale.getdefaultlocale()
        if sys_lang:
            lang_code = sys_lang.replace("-", "_")
            if lang_code in LANGUAGES:
                return lang_code
            base = lang_code.split("_")[0]
            for code in LANGUAGES:
                if code.startswith(base):
                    return code
    except Exception:
        pass
    return "en_US"
