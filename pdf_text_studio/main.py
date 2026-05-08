from __future__ import annotations

import sys
import tkinter as tk

from pdf_text_studio.app.editor import EditorApplication
from pdf_text_studio.ui.main_window import MainWindow

VERSION = "0.42"


def run():
    root = tk.Tk()
    path = sys.argv[1] if len(sys.argv) >= 2 else None
    app = EditorApplication(path)
    MainWindow(root, app, VERSION)

    def _on_close():
        app.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)
    root.mainloop()


if __name__ == '__main__':
    run()
