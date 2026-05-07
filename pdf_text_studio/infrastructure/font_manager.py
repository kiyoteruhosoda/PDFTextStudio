from __future__ import annotations

import os


class FontManager:
    def __init__(self):
        self._fonts: dict[str, str | None] = {}
        self._register_default()

    def _register_default(self):
        for candidate in ["NotoSansJP-Regular.ttf", "NotoSansCJKjp-Regular.otf"]:
            path = os.path.join(os.getcwd(), candidate)
            if os.path.exists(path):
                self._fonts[os.path.splitext(candidate)[0]] = path
                return
        self._fonts["Helvetica"] = None

    def names(self) -> list[str]:
        return list(self._fonts.keys())

    def path_of(self, name: str) -> str | None:
        return self._fonts.get(name)

    def add_font(self, path: str) -> str:
        name = os.path.splitext(os.path.basename(path))[0]
        self._fonts[name] = path
        return name
