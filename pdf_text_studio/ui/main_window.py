from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from tkinter import filedialog, messagebox, simpledialog

import fitz
from PIL import Image, ImageTk, ImageDraw, ImageFont

from pdf_text_studio.app.editor import EditorApplication
from pdf_text_studio.domain.models import Coordinate


class MainWindow:
    def __init__(self, root: tk.Tk, app: EditorApplication, version: str):
        self.root, self.app, self.version = root, app, version
        self.entry = None
        self.pan_offset = [0.0, 0.0]
        self.pan_start = (0.0, 0.0)
        self.panning = False
        self.drag_before = None
        self.selected_item = None
        self._build_ui()
        self.render()

    def _font(self, item):
        return ImageFont.truetype(item.font_path, int(item.font_size * self.app.scale)) if item.font_path else ImageFont.load_default()

    def _editable(self) -> bool:
        if self.app.is_preview_mode:
            self.status.set("Preview中は編集できません。Back to Editで戻ってください。")
            return False
        return True

    def _build_ui(self):
        self.root.title(f"PDFTextStudio v{self.version}")
        self.root.geometry("760x760")
        menubar = tk.Menu(self.root); filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Open", command=self.open_pdf); filem.add_command(label="Save", command=self.save_pdf)
        menubar.add_cascade(label="File", menu=filem); self.root.config(menu=menubar)

        tb = tk.Frame(self.root); tb.pack(fill=tk.X)
        self.font_var = tk.StringVar(value=self.app.current_font_name); self.size_var = tk.IntVar(value=self.app.current_font_size)
        self.font_menu = tk.OptionMenu(tb, self.font_var, *self.app.font_manager.names()); self.font_menu.pack(side=tk.LEFT)
        tk.Button(tb, text="Add Font", command=self.add_font).pack(side=tk.LEFT)
        tk.OptionMenu(tb, self.size_var, *[8,10,12,14,16,18,20,24,32]).pack(side=tk.LEFT)
        tk.Button(tb, text="Preview Export", command=self.preview_export).pack(side=tk.LEFT)
        tk.Button(tb, text="Back to Edit", command=self.back_to_edit).pack(side=tk.LEFT)

        ops = tk.Frame(self.root); ops.pack(fill=tk.X)
        for t, c in [("Prev", self.prev_page), ("Next", self.next_page), ("Undo", self.undo), ("Redo", self.redo)]:
            tk.Button(ops, text=t, command=c).pack(side=tk.LEFT)

        self.status = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status, anchor="w").pack(fill=tk.X, side=tk.BOTTOM)

        self.canvas = tk.Canvas(self.root, bg="white"); self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_add); self.canvas.bind("<Button-3>", self.on_select)
        self.canvas.bind("<B3-Motion>", self.on_drag); self.canvas.bind("<ButtonRelease-3>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click); self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.root.bind("<Delete>", self.on_delete)

    def render(self):
        self.canvas.delete("all")
        page = self.app.doc.load_page(self.app.page_index)
        self.app.page_width, self.app.page_height = page.rect.width, page.rect.height
        pix = page.get_pixmap(matrix=fitz.Matrix(self.app.scale, self.app.scale))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        draw = ImageDraw.Draw(img)
        if not self.app.is_preview_mode:
            for it in self.app.elements_by_page.get(self.app.page_index, []):
                font = self._font(it)
                asc, des = font.getmetrics()
                x, y_top = it.coordinate.pdf_baseline_to_gui_top(self.app.scale, self.app.page_height, (0, 0), asc)
                draw.text((x, y_top), it.text, font=font, fill="black")
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.create_image(self.pan_offset[0], self.pan_offset[1], image=self.tk_img, anchor="nw")

    def _find_hit(self, e):
        for item in reversed(self.app.elements_by_page.get(self.app.page_index, [])):
            font = self._font(item)
            asc, des = font.getmetrics(); w = font.getlength(item.text) if hasattr(font, "getlength") else font.getsize(item.text)[0]
            x, y_top = item.coordinate.pdf_baseline_to_gui_top(self.app.scale, self.app.page_height, tuple(self.pan_offset), asc)
            if x <= e.x <= x + w and y_top <= e.y <= y_top + asc + des:
                return item, x, y_top
        return None, 0, 0

    def on_add(self, e):
        if not self._editable():
            return
        if self._find_hit(e)[0]:
            return
        font_name = self.font_var.get(); font_path = self.app.font_manager.path_of(font_name)
        if font_path is None:
            messagebox.showerror("フォントエラー", "TTF/OTFフォントを選択してください")
            return
        tmp_font = ImageFont.truetype(font_path, int(self.size_var.get() * self.app.scale)); asc, _ = tmp_font.getmetrics()
        coord = Coordinate.gui_to_pdf_baseline(e.x, e.y, self.app.scale, self.app.page_height, tuple(self.pan_offset), asc)
        self.show_entry(e.x, e.y, font_name, self.size_var.get(), lambda txt: self._commit_add(txt, coord, font_name))

    def _commit_add(self, txt, coord, font_name):
        if txt:
            self.app.add_text(coord, txt, font_name, self.size_var.get()); self.render()

    def on_select(self, e):
        if not self._editable():
            return
        item, x, y_top = self._find_hit(e)
        self.app.drag_item = item; self.selected_item = item
        if item:
            self.drag_before = replace(item); self.app.drag_offset = (e.x - x, e.y - y_top); self.panning = False
        else:
            self.panning = True; self.pan_start = (e.x, e.y)

    def on_drag(self, e):
        if not self._editable():
            return
        if self.app.drag_item:
            font = self._font(self.app.drag_item); asc, _ = font.getmetrics()
            nx, ny = e.x - self.app.drag_offset[0], e.y - self.app.drag_offset[1]
            self.app.drag_item.coordinate = Coordinate.gui_to_pdf_baseline(nx, ny, self.app.scale, self.app.page_height, tuple(self.pan_offset), asc)
            self.render()
        elif self.panning:
            dx, dy = e.x - self.pan_start[0], e.y - self.pan_start[1]; self.pan_offset[0] += dx; self.pan_offset[1] += dy; self.pan_start = (e.x, e.y); self.render()

    def on_release(self, _):
        if self.app.drag_item and self.drag_before:
            self.app.move_text(self.drag_before, replace(self.app.drag_item))
        self.drag_before = None; self.panning = False

    def on_delete(self, _):
        if not self._editable():
            return
        if self.selected_item:
            self.app.delete_text(self.selected_item)
            self.selected_item = None
            self.render()

    def on_double_click(self, e):
        if not self._editable():
            return
        item, _, _ = self._find_hit(e)
        if not item:
            return
        new_text = simpledialog.askstring("Edit Text", "テキストを編集", initialvalue=item.text)
        if new_text is None:
            return
        before = replace(item)
        item.text = new_text
        item.font_size = float(self.size_var.get())
        item.font_name = self.font_var.get()
        item.font_path = self.app.font_manager.path_of(item.font_name)
        self.app.edit_text(before, replace(item))
        self.render()

    def on_zoom(self, e): self.app.scale *= 1.2 if e.delta > 0 else 1 / 1.2; self.render()
    def undo(self):
        if not self._editable():
            return
        self.app.undo(); self.render()

    def redo(self):
        if not self._editable():
            return
        self.app.redo(); self.render()
    def next_page(self):
        if self.app.page_index < len(self.app.doc) - 1: self.app.page_index += 1; self.render()
    def prev_page(self):
        if self.app.page_index > 0: self.app.page_index -= 1; self.render()

    def preview_export(self):
        ok, msg, path = self.app.create_preview(); self.status.set(msg)
        if ok and path:
            self.app.load_preview(path); self.render()

    def save_pdf(self):
        if self.app.is_preview_mode:
            self.status.set("Preview中は保存できません。Back to Edit で戻ってから保存してください。")
            return
        out = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[('PDF', '*.pdf')])
        if not out: return
        ok, msg = self.app.save(out); self.status.set(msg)

    def open_pdf(self):
        path = filedialog.askopenfilename(filetypes=[('PDF', '*.pdf')])
        if not path: return
        self._clear_interaction_state()
        self.app.cleanup_preview()
        self.app.__init__(path); self.font_var.set(self.app.current_font_name); self.pan_offset = [0.0, 0.0]; self.render()

    def back_to_edit(self):
        self._clear_interaction_state()
        self.app.load_source()
        self.render()


    def _clear_interaction_state(self):
        self.selected_item = None
        self.app.drag_item = None
        self.drag_before = None
        self.panning = False

    def add_font(self):
        path = filedialog.askopenfilename(filetypes=[('Font', '*.ttf *.otf')])
        if not path: return
        name = self.app.font_manager.add_font(path); self.font_menu['menu'].add_command(label=name, command=tk._setit(self.font_var, name)); self.font_var.set(name)

    def show_entry(self, x, y, font_name, font_size, on_commit):
        if self.entry: self.entry.destroy()
        self.entry = tk.Entry(self.canvas, font=(font_name, int(font_size * self.app.scale))); self.entry.place(x=x, y=y); self.entry.focus_set()
        def commit(_=None):
            if not self.entry: return
            txt = self.entry.get(); self.entry.destroy(); self.entry = None; on_commit(txt)
        self.entry.bind('<Return>', commit); self.entry.bind('<FocusOut>', commit)
