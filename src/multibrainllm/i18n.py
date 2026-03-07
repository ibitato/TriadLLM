from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from multibrainllm.domain import LanguageCode


@lru_cache(maxsize=8)
def _load_catalog(language: LanguageCode) -> dict[str, str]:
    resource = files("multibrainllm").joinpath("locales", f"{language}.json")
    return json.loads(resource.read_text(encoding="utf-8"))


class Translator:
    def __init__(self, language: LanguageCode = "en") -> None:
        self.language = language

    def set_language(self, language: LanguageCode) -> None:
        self.language = language

    def t(self, key: str, **kwargs: Any) -> str:
        active = _load_catalog(self.language)
        fallback = _load_catalog("en")
        template = active.get(key, fallback.get(key, key))
        return template.format(**kwargs)
