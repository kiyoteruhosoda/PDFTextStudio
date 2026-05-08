from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from pdf_text_studio.app.editor import EditorApplication
from pdf_text_studio.ui.main_window import MainWindow

VERSION = "0.42"


def _resolve_launch_path(argv: list[str]) -> str | None:
    if len(argv) < 2:
        return None
    candidate = argv[1].strip()
    if not candidate:
        return None
    path = Path(candidate)
    return str(path) if path.exists() else None


def run():
    qt_app = QApplication(sys.argv)
    path = _resolve_launch_path(sys.argv)
    app = EditorApplication(path)
    window = MainWindow(app, VERSION)
    window.show()
    exit_code = qt_app.exec()
    app.shutdown()
    raise SystemExit(exit_code)


if __name__ == '__main__':
    run()
