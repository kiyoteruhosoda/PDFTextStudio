from __future__ import annotations

import sys
import tkinter as tk
from tkinter import filedialog

from pdf_text_studio.app.editor import EditorApplication
from pdf_text_studio.ui.main_window import MainWindow

VERSION = "0.42"


def run():
    root = tk.Tk()
    root.withdraw()
    path = sys.argv[1] if len(sys.argv) >= 2 else filedialog.askopenfilename(filetypes=[('PDF', '*.pdf')])
    if not path:
        print('No file selected.')
        return
    root.deiconify()
    app = EditorApplication(path)
    MainWindow(root, app, VERSION)
    root.mainloop()


if __name__ == '__main__':
    run()
