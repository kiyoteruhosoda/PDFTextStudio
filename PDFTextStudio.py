"""
PDFTextStudio
-------------
PDF座標（pt）を正として扱い、GUI座標（px）は表示時のみ変換する。
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, replace
from typing import Literal

import fitz
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageDraw, ImageFont

VERSION = 0.40


# --- Domain ---
OperationType = Literal["add_text", "move_text", "delete_text"]


@dataclass
class Coordinate:
    x_pt: float
    y_pt: float

    @staticmethod
    def gui_to_pdf(x_px: float, y_px: float, zoom: float, page_height_pt: float, pan_offset: tuple[float, float]) -> "Coordinate":
        offset_x, offset_y = pan_offset
        x_pt = (x_px - offset_x) / zoom
        y_pt = page_height_pt - ((y_px - offset_y) / zoom)
        return Coordinate(x_pt=x_pt, y_pt=y_pt)

    def to_gui(self, zoom: float, page_height_pt: float, pan_offset: tuple[float, float]) -> tuple[float, float]:
        offset_x, offset_y = pan_offset
        x_px = self.x_pt * zoom + offset_x
        y_px = (page_height_pt - self.y_pt) * zoom + offset_y
        return x_px, y_px


@dataclass
class TextElement:
    element_id: int
    page_index: int
    text: str
    coordinate: Coordinate
    font_size: float
    font_name: str
    font_path: str | None


@dataclass
class EditOperation:
    operation_type: OperationType
    page_index: int
    element_id: int
    before: TextElement | None
    after: TextElement | None


# --- Infrastructure ---
class FontManager:
    def __init__(self) -> None:
        self.fonts: dict[str, str | None] = {}
        self._register_default()

    def _register_default(self) -> None:
        candidates = [
            os.path.join(os.getcwd(), "NotoSansJP-Regular.ttf"),
            os.path.join(os.getcwd(), "NotoSansCJKjp-Regular.otf"),
        ]
        for p in candidates:
            if os.path.exists(p):
                self.fonts[os.path.splitext(os.path.basename(p))[0]] = p
                return
        self.fonts["Helvetica"] = None

    def add_font(self, path: str) -> str:
        name = os.path.splitext(os.path.basename(path))[0]
        self.fonts[name] = path
        return name

    def is_registered(self, font_name: str) -> bool:
        return font_name in self.fonts

    def path_of(self, font_name: str) -> str | None:
        return self.fonts.get(font_name)

    def names(self) -> list[str]:
        return list(self.fonts.keys())


# --- Model ---
class PDFModel:
    def __init__(self, path: str):
        self.path = path
        self.doc = fitz.open(path)
        self.page_index = 0
        self.page_width, self.page_height = self._get_size(0)
        self.scale = 1.5
        self.elements_by_page: dict[int, list[TextElement]] = {}
        self.undo_stack: list[EditOperation] = []
        self.redo_stack: list[EditOperation] = []
        self.font_manager = FontManager()
        self.current_font_name = self.font_manager.names()[0]
        self.current_font_size = 16
        self.drag_item: TextElement | None = None
        self.drag_offset = (0.0, 0.0)
        self._id_seq = 1

    def _get_size(self, idx: int) -> tuple[float, float]:
        r = self.doc.load_page(idx).rect
        return r.width, r.height

    def _find_element(self, page_index: int, element_id: int) -> TextElement | None:
        for e in self.elements_by_page.get(page_index, []):
            if e.element_id == element_id:
                return e
        return None

    def apply_operation(self, operation: EditOperation, push_undo: bool = True) -> None:
        if operation.operation_type == "add_text" and operation.after is not None:
            self.elements_by_page.setdefault(operation.page_index, []).append(operation.after)
        elif operation.operation_type == "move_text" and operation.after is not None:
            target = self._find_element(operation.page_index, operation.element_id)
            if target:
                target.coordinate = operation.after.coordinate
        elif operation.operation_type == "delete_text":
            target = self._find_element(operation.page_index, operation.element_id)
            if target:
                self.elements_by_page[operation.page_index].remove(target)

        if push_undo:
            self.undo_stack.append(operation)
            self.redo_stack.clear()

    def reverse_operation(self, operation: EditOperation) -> None:
        if operation.operation_type == "add_text" and operation.after is not None:
            target = self._find_element(operation.page_index, operation.element_id)
            if target:
                self.elements_by_page[operation.page_index].remove(target)
        elif operation.operation_type == "move_text" and operation.before is not None:
            target = self._find_element(operation.page_index, operation.element_id)
            if target:
                target.coordinate = operation.before.coordinate
        elif operation.operation_type == "delete_text" and operation.before is not None:
            self.elements_by_page.setdefault(operation.page_index, []).append(operation.before)

    def add_text(self, coordinate: Coordinate, text: str, font_size: float, font_name: str) -> None:
        font_path = self.font_manager.path_of(font_name)
        element = TextElement(
            element_id=self._id_seq,
            page_index=self.page_index,
            text=text,
            coordinate=coordinate,
            font_size=font_size,
            font_name=font_name,
            font_path=font_path,
        )
        self._id_seq += 1
        self.apply_operation(EditOperation("add_text", self.page_index, element.element_id, None, element))

    def move_text(self, item: TextElement, new_coordinate: Coordinate, push_undo: bool) -> None:
        before = replace(item)
        before.coordinate = Coordinate(item.coordinate.x_pt, item.coordinate.y_pt)
        item.coordinate = new_coordinate
        after = replace(item)
        if push_undo:
            self.undo_stack.append(EditOperation("move_text", self.page_index, item.element_id, before, after))
            self.redo_stack.clear()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        operation = self.undo_stack.pop()
        self.reverse_operation(operation)
        self.redo_stack.append(operation)

    def redo(self) -> None:
        if not self.redo_stack:
            return
        operation = self.redo_stack.pop()
        self.apply_operation(operation, push_undo=False)
        self.undo_stack.append(operation)

    def save_pdf(self, out_path: str) -> tuple[bool, str]:
        out_doc = fitz.open(self.path)
        for page_idx, elements in self.elements_by_page.items():
            page = out_doc.load_page(page_idx)
            for el in elements:
                if not el.font_path:
                    return False, f"日本語フォントが未設定です: {el.font_name}"
                page.insert_text(
                    point=(el.coordinate.x_pt, el.coordinate.y_pt),
                    text=el.text,
                    fontsize=el.font_size,
                    fontfile=el.font_path,
                    color=(0, 0, 0),
                    overlay=True,
                )
        out_doc.save(out_path)
        out_doc.close()
        return True, "Saved"


class PDFView:
    def __init__(self, root, model):
        self.root = root
        self.model = model
        self.entry = None
        self._build_ui()

    def _build_ui(self):
        self.root.title(f"PDFTextStudio v{VERSION}")
        self.root.geometry('750x750')
        self.root.configure(bg='#f4f4f4')
        menubar = tk.Menu(self.root)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label='Open', command=self.on_open)
        filem.add_command(label='Save', command=self.on_save)
        filem.add_separator()
        filem.add_command(label='Exit', command=self.root.quit)
        menubar.add_cascade(label='File', menu=filem)
        self.root.config(menu=menubar)

        tb = tk.Frame(self.root, bg='#e0e0e0', pady=8)
        tb.pack(fill=tk.X, padx=0, pady=(0, 2))
        tk.Label(tb, text='Font:', bg='#e0e0e0').pack(side=tk.LEFT, padx=(10, 2))
        self.font_var = tk.StringVar(value=self.model.current_font_name)
        self.font_menu = tk.OptionMenu(tb, self.font_var, *self.model.font_manager.names())
        self.font_menu.pack(side=tk.LEFT, padx=2)
        tk.Button(tb, text='Add Font', command=self.on_add_font).pack(side=tk.LEFT, padx=8)

        tk.Label(tb, text='Size:', bg='#e0e0e0').pack(side=tk.LEFT, padx=(10, 2))
        self.size_var = tk.IntVar(value=self.model.current_font_size)
        self.size_menu = tk.OptionMenu(tb, self.size_var, *[8, 10, 12, 14, 16, 18, 20, 24, 28, 32])
        self.size_menu.pack(side=tk.LEFT, padx=2)

        ctrl = tk.Frame(self.root, bg='#f4f4f4')
        ctrl.pack(fill=tk.X, padx=0, pady=(0, 8))
        for txt, cmd in [('Prev', self.on_prev), ('Next', self.on_next), ('Undo', self.on_undo), ('Redo', self.on_redo)]:
            tk.Button(ctrl, text=txt, command=cmd).pack(side=tk.LEFT, padx=6)

        self.status = tk.StringVar()
        tk.Label(self.root, textvariable=self.status, anchor='w').pack(fill=tk.X, side=tk.BOTTOM)

        self.canvas = tk.Canvas(self.root, bg='white', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        self.canvas.bind('<Button-1>', self.on_add)
        self.canvas.bind('<MouseWheel>', self.on_zoom)
        self.canvas.bind('<Button-3>', self.on_select)
        self.canvas.bind('<B3-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-3>', self.on_release)

    def render(self):
        self.canvas.delete('all')
        page = self.model.doc.load_page(self.model.page_index)
        self.model.page_width, self.model.page_height = page.rect.width, page.rect.height
        pix = page.get_pixmap(matrix=fitz.Matrix(self.model.scale, self.model.scale))
        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        draw = ImageDraw.Draw(img)
        for it in self.model.elements_by_page.get(self.model.page_index, []):
            x, y = it.coordinate.to_gui(self.model.scale, self.model.page_height, tuple(self.controller.pan_offset))
            font = ImageFont.truetype(it.font_path, int(it.font_size * self.model.scale)) if it.font_path else ImageFont.load_default()
            draw.text((x - self.controller.pan_offset[0], y - self.controller.pan_offset[1]), it.text, font=font, fill='black')
        self.tk_img = ImageTk.PhotoImage(img)
        ox, oy = self.controller.pan_offset
        self.canvas.create_image(ox, oy, image=self.tk_img, anchor='nw')

    def show_text_entry(self, x_canvas, y_canvas, font_name, font_size, on_commit):
        if self.entry:
            self.entry.destroy()
        self.entry = tk.Entry(self.canvas, font=(font_name, int(font_size * self.model.scale)))
        self.entry.place(x=x_canvas, y=y_canvas)
        self.entry.focus_set()

        def commit(_event=None):
            text = self.entry.get()
            self.entry.destroy()
            self.entry = None
            on_commit(text)

        self.entry.bind('<Return>', commit)
        self.entry.bind('<FocusOut>', commit)

    def on_add(self, e): self.controller.add_text(e)
    def on_zoom(self, e): self.controller.zoom(e)
    def on_select(self, e): self.controller.select(e)
    def on_drag(self, e): self.controller.drag(e)
    def on_release(self, e): self.controller.release(e)
    def on_prev(self): self.controller.prev()
    def on_next(self): self.controller.next()
    def on_undo(self): self.controller.undo()
    def on_redo(self): self.controller.redo()
    def on_save(self): self.controller.save()

    def on_add_font(self):
        path = filedialog.askopenfilename(filetypes=[('Font', '*.ttf *.otf')])
        if not path:
            return
        name = self.model.font_manager.add_font(path)
        self.font_menu['menu'].add_command(label=name, command=tk._setit(self.font_var, name))
        self.font_var.set(name)

    def on_open(self):
        path = filedialog.askopenfilename(filetypes=[('PDF', '*.pdf')])
        if not path:
            return
        self.model.__init__(path)
        self.font_var.set(self.model.current_font_name)
        self.render()


class PDFController:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        view.controller = self
        self.panning = False
        self.pan_start = (0, 0)
        self.pan_offset = [0, 0]
        self.drag_before: TextElement | None = None
        view.render()

    def add_text(self, e):
        coord = Coordinate.gui_to_pdf(e.x, e.y, self.model.scale, self.model.page_height, tuple(self.pan_offset))
        font_name = self.view.font_var.get()
        font_size = self.view.size_var.get()

        def on_commit(txt):
            if txt:
                self.model.add_text(coord, txt, font_size, font_name)
                self.view.render()

        self.view.show_text_entry(e.x, e.y, font_name, font_size, on_commit)

    def select(self, e):
        rx, ry = e.x, e.y
        self.model.drag_item = None
        for it in self.model.elements_by_page.get(self.model.page_index, []):
            x, y = it.coordinate.to_gui(self.model.scale, self.model.page_height, tuple(self.pan_offset))
            font = ImageFont.truetype(it.font_path, int(it.font_size * self.model.scale)) if it.font_path else ImageFont.load_default()
            width = font.getlength(it.text) if hasattr(font, 'getlength') else font.getsize(it.text)[0]
            asc, des = font.getmetrics()
            if x <= rx <= x + width and y <= ry <= y + asc + des:
                self.model.drag_item = it
                self.drag_before = replace(it)
                self.model.drag_offset = (rx - x, ry - y)
                self.panning = False
                break
        else:
            self.panning = True
            self.pan_start = (rx, ry)

    def drag(self, e):
        if self.model.drag_item:
            nx = e.x - self.model.drag_offset[0]
            ny = e.y - self.model.drag_offset[1]
            coord = Coordinate.gui_to_pdf(nx, ny, self.model.scale, self.model.page_height, tuple(self.pan_offset))
            self.model.move_text(self.model.drag_item, coord, push_undo=False)
            self.view.render()
        elif self.panning:
            dx, dy = e.x - self.pan_start[0], e.y - self.pan_start[1]
            self.pan_offset[0] += dx
            self.pan_offset[1] += dy
            self.pan_start = (e.x, e.y)
            self.view.render()

    def release(self, _e):
        if self.model.drag_item and self.drag_before:
            after = replace(self.model.drag_item)
            self.model.undo_stack.append(EditOperation("move_text", self.model.page_index, self.model.drag_item.element_id, self.drag_before, after))
            self.model.redo_stack.clear()
            self.model.drag_item = None
            self.drag_before = None
        self.panning = False
        self.view.render()

    def save(self):
        path = filedialog.asksaveasfilename(defaultextension='.pdf')
        if not path:
            return
        if os.path.abspath(path) == os.path.abspath(self.model.path):
            self.view.status.set('同名上書きは禁止です。別名保存してください。')
            return
        ok, message = self.model.save_pdf(path)
        self.view.status.set(message)
        if ok:
            self.model.doc = fitz.open(path)
            self.model.path = path
            self.view.render()

    def redo(self): self.model.redo(); self.view.render()
    def undo(self): self.model.undo(); self.view.render()
    def next(self):
        if self.model.page_index < len(self.model.doc) - 1:
            self.model.page_index += 1
            self.view.render()

    def prev(self):
        if self.model.page_index > 0:
            self.model.page_index -= 1
            self.view.render()

    def zoom(self, e):
        self.model.scale *= 1.2 if e.delta > 0 else 1 / 1.2
        self.view.render()


def main():
    r = tk.Tk()
    r.withdraw()
    pdf_path = sys.argv[1] if len(sys.argv) >= 2 else filedialog.askopenfilename(filetypes=[('PDF', '*.pdf')])
    if not pdf_path:
        print('No file selected.')
        sys.exit()
    r.deiconify()
    m = PDFModel(pdf_path)
    v = PDFView(r, m)
    PDFController(m, v)
    r.mainloop()


if __name__ == '__main__':
    main()
