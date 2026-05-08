from __future__ import annotations

import sys
from pathlib import Path
import tkinter as tk

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
    root = tk.Tk()
    path = _resolve_launch_path(sys.argv)
    app = EditorApplication(path)
    MainWindow(root, app, VERSION)

    def _on_close():
        app.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)
    root.mainloop()


if __name__ == '__main__':
    run()
