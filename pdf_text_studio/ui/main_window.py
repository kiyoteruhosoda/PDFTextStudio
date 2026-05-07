from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from tkinter import filedialog, messagebox

import fitz
from PIL import Image, ImageTk, ImageDraw, ImageFont

from pdf_text_studio.app.editor import EditorApplication
from pdf_text_studio.domain.models import Coordinate


class MainWindow:
    def __init__(self, root: tk.Tk, app: EditorApplication, version: str):
        self.root = root
        self.app = app
        self.version = version
        self.entry = None
        self.pan_offset = [0.0, 0.0]
        self.pan_start = (0.0, 0.0)
        self.panning = False
        self.drag_before = None
        self._build_ui()
        self.render()

    def _build_ui(self):
        self.root.title(f"PDFTextStudio v{self.version}")
        self.root.geometry("760x760")
        menubar = tk.Menu(self.root)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Open", command=self.open_pdf)
        filem.add_command(label="Save", command=self.save_pdf)
        filem.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filem)
        self.root.config(menu=menubar)

        tb = tk.Frame(self.root)
        tb.pack(fill=tk.X)
        self.font_var = tk.StringVar(value=self.app.current_font_name)
        self.size_var = tk.IntVar(value=self.app.current_font_size)
        self.font_menu = tk.OptionMenu(tb, self.font_var, *self.app.font_manager.names())
        self.font_menu.pack(side=tk.LEFT)
        tk.Button(tb, text="Add Font", command=self.add_font).pack(side=tk.LEFT)
        tk.OptionMenu(tb, self.size_var, *[8,10,12,14,16,18,20,24,32]).pack(side=tk.LEFT)

        ops = tk.Frame(self.root)
        ops.pack(fill=tk.X)
        for t, c in [("Prev", self.prev_page), ("Next", self.next_page), ("Undo", self.undo), ("Redo", self.redo)]:
            tk.Button(ops, text=t, command=c).pack(side=tk.LEFT)

        self.status = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status, anchor="w").pack(fill=tk.X, side=tk.BOTTOM)

        self.canvas = tk.Canvas(self.root, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_add)
        self.canvas.bind("<Button-3>", self.on_select)
        self.canvas.bind("<B3-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_release)
        self.canvas.bind("<MouseWheel>", self.on_zoom)

    def render(self):
        self.canvas.delete("all")
        page = self.app.doc.load_page(self.app.page_index)
        self.app.page_width, self.app.page_height = page.rect.width, page.rect.height
        pix = page.get_pixmap(matrix=fitz.Matrix(self.app.scale, self.app.scale))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        draw = ImageDraw.Draw(img)
        for it in self.app.elements_by_page.get(self.app.page_index, []):
            x, y = it.coordinate.pdf_to_gui(self.app.scale, self.app.page_height, (0, 0))
            font = ImageFont.truetype(it.font_path, int(it.font_size * self.app.scale)) if it.font_path else ImageFont.load_default()
            draw.text((x, y), it.text, font=font, fill="black")
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.create_image(self.pan_offset[0], self.pan_offset[1], image=self.tk_img, anchor="nw")

    def on_add(self, e):
        coord = Coordinate.gui_to_pdf(e.x, e.y, self.app.scale, self.app.page_height, tuple(self.pan_offset))
        font_name = self.font_var.get()
        if self.app.font_manager.path_of(font_name) is None:
            messagebox.showwarning("フォント警告", "TTF/OTF フォントを選択してください。")
        self.show_entry(e.x, e.y, font_name, self.size_var.get(), lambda txt: self._commit_add(txt, coord, font_name))

    def _commit_add(self, txt, coord, font_name):
        if txt:
            self.app.add_text(coord, txt, font_name, self.size_var.get())
            self.render()

    def on_select(self, e):
        self.app.drag_item = None
        for item in self.app.elements_by_page.get(self.app.page_index, []):
            x, y = item.coordinate.pdf_to_gui(self.app.scale, self.app.page_height, tuple(self.pan_offset))
            font = ImageFont.truetype(item.font_path, int(item.font_size * self.app.scale)) if item.font_path else ImageFont.load_default()
            w = font.getlength(item.text) if hasattr(font, "getlength") else font.getsize(item.text)[0]
            h = sum(font.getmetrics())
            if x <= e.x <= x + w and y <= e.y <= y + h:
                self.app.drag_item = item
                self.drag_before = replace(item)
                self.app.drag_offset = (e.x - x, e.y - y)
                return
        self.panning = True
        self.pan_start = (e.x, e.y)

    def on_drag(self, e):
        if self.app.drag_item:
            nx, ny = e.x - self.app.drag_offset[0], e.y - self.app.drag_offset[1]
            self.app.drag_item.coordinate = Coordinate.gui_to_pdf(nx, ny, self.app.scale, self.app.page_height, tuple(self.pan_offset))
            self.render()
        elif self.panning:
            dx, dy = e.x - self.pan_start[0], e.y - self.pan_start[1]
            self.pan_offset[0] += dx
            self.pan_offset[1] += dy
            self.pan_start = (e.x, e.y)
            self.render()

    def on_release(self, _):
        if self.app.drag_item and self.drag_before:
            self.app.move_text(self.drag_before, replace(self.app.drag_item))
        self.app.drag_item = None
        self.drag_before = None
        self.panning = False

    def on_zoom(self, e): self.app.scale *= 1.2 if e.delta > 0 else 1 / 1.2; self.render()
    def undo(self): self.app.undo(); self.render()
    def redo(self): self.app.redo(); self.render()
    def next_page(self):
        if self.app.page_index < len(self.app.doc) - 1: self.app.page_index += 1; self.render()
    def prev_page(self):
        if self.app.page_index > 0: self.app.page_index -= 1; self.render()

    def save_pdf(self):
        out = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[('PDF', '*.pdf')])
        if not out:
            return
        ok, msg = self.app.save(out)
        self.status.set(msg)
        if ok:
            self.app.preview_saved_pdf(out)
            self.render()

    def open_pdf(self):
        path = filedialog.askopenfilename(filetypes=[('PDF', '*.pdf')])
        if not path:
            return
        self.app.__init__(path)
        self.font_var.set(self.app.current_font_name)
        self.pan_offset = [0.0, 0.0]
        self.render()

    def add_font(self):
        path = filedialog.askopenfilename(filetypes=[('Font', '*.ttf *.otf')])
        if not path:
            return
        name = self.app.font_manager.add_font(path)
        self.font_menu['menu'].add_command(label=name, command=tk._setit(self.font_var, name))
        self.font_var.set(name)

    def show_entry(self, x, y, font_name, font_size, on_commit):
        if self.entry:
            self.entry.destroy()
        self.entry = tk.Entry(self.canvas, font=(font_name, int(font_size * self.app.scale)))
        self.entry.place(x=x, y=y)
        self.entry.focus_set()
        def commit(_=None):
            if not self.entry:
                return
            txt = self.entry.get()
            self.entry.destroy()
            self.entry = None
            on_commit(txt)
        self.entry.bind('<Return>', commit)
        self.entry.bind('<FocusOut>', commit)
