from __future__ import annotations

import os
import sys
from dataclasses import dataclass, replace
from abc import ABC, abstractmethod

import fitz
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont

VERSION = 0.41


@dataclass(frozen=True)
class Coordinate:
    x_pt: float
    y_pt: float

    @staticmethod
    def gui_to_pdf(x_px: float, y_px: float, zoom: float, page_height_pt: float, pan_offset: tuple[float, float]) -> "Coordinate":
        ox, oy = pan_offset
        return Coordinate((x_px - ox) / zoom, page_height_pt - ((y_px - oy) / zoom))

    def pdf_to_gui(self, zoom: float, page_height_pt: float, pan_offset: tuple[float, float]) -> tuple[float, float]:
        ox, oy = pan_offset
        return (self.x_pt * zoom) + ox, ((page_height_pt - self.y_pt) * zoom) + oy


@dataclass
class TextElement:
    element_id: int
    page_index: int
    text: str
    coordinate: Coordinate
    font_size: float
    font_name: str
    font_path: str | None


class EditOperation(ABC):
    def __init__(self, page_index: int, element_id: int):
        self.page_index = page_index
        self.element_id = element_id

    @abstractmethod
    def execute(self, model: "PDFModel") -> None:
        ...

    @abstractmethod
    def undo(self, model: "PDFModel") -> None:
        ...


class AddTextOperation(EditOperation):
    def __init__(self, element: TextElement):
        super().__init__(element.page_index, element.element_id)
        self.element = element

    def execute(self, model: "PDFModel") -> None:
        model.elements_by_page.setdefault(self.page_index, []).append(self.element)

    def undo(self, model: "PDFModel") -> None:
        target = model.find_element(self.page_index, self.element_id)
        if target:
            model.elements_by_page[self.page_index].remove(target)


class MoveTextOperation(EditOperation):
    def __init__(self, before: TextElement, after: TextElement):
        super().__init__(after.page_index, after.element_id)
        self.before = before
        self.after = after

    def execute(self, model: "PDFModel") -> None:
        target = model.find_element(self.page_index, self.element_id)
        if target:
            target.coordinate = self.after.coordinate

    def undo(self, model: "PDFModel") -> None:
        target = model.find_element(self.page_index, self.element_id)
        if target:
            target.coordinate = self.before.coordinate


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


class PDFModel:
    def __init__(self, path: str):
        self.path = path
        self.doc = fitz.open(path)
        self.page_index = 0
        rect = self.doc.load_page(0).rect
        self.page_width, self.page_height = rect.width, rect.height
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

    def find_element(self, page_index: int, element_id: int) -> TextElement | None:
        for element in self.elements_by_page.get(page_index, []):
            if element.element_id == element_id:
                return element
        return None

    def apply_operation(self, op: EditOperation, record_history: bool = True):
        op.execute(self)
        if record_history:
            self.undo_stack.append(op)
            self.redo_stack.clear()

    def add_text(self, coord: Coordinate, text: str, font_name: str, font_size: float):
        element = TextElement(
            element_id=self._id_seq,
            page_index=self.page_index,
            text=text,
            coordinate=coord,
            font_size=font_size,
            font_name=font_name,
            font_path=self.font_manager.path_of(font_name),
        )
        self._id_seq += 1
        self.apply_operation(AddTextOperation(element))

    def undo(self):
        if not self.undo_stack:
            return
        op = self.undo_stack.pop()
        op.undo(self)
        self.redo_stack.append(op)

    def redo(self):
        if not self.redo_stack:
            return
        op = self.redo_stack.pop()
        op.execute(self)
        self.undo_stack.append(op)

    def save_pdf(self, out_path: str) -> tuple[bool, str]:
        if os.path.abspath(out_path) == os.path.abspath(self.path):
            return False, "元PDFへの上書きは禁止です。別名保存してください。"
        out_doc = fitz.open(self.path)
        for page_idx, elements in self.elements_by_page.items():
            page = out_doc.load_page(page_idx)
            for el in elements:
                if not el.font_path:
                    out_doc.close()
                    return False, f"フォント未設定: {el.font_name}。日本語フォントを選択してください。"
                page.insert_text(
                    (el.coordinate.x_pt, el.coordinate.y_pt),
                    el.text,
                    fontsize=el.font_size,
                    fontfile=el.font_path,
                    overlay=True,
                )
        out_doc.save(out_path)
        out_doc.close()
        return True, "保存しました。"


class PDFView:
    def __init__(self, root: tk.Tk, model: PDFModel):
        self.root = root
        self.model = model
        self.entry: tk.Entry | None = None
        self._build_ui()

    def _build_ui(self):
        self.root.title(f"PDFTextStudio v{VERSION}")
        self.root.geometry("760x760")

        menubar = tk.Menu(self.root)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Open", command=self.on_open)
        filem.add_command(label="Save", command=self.on_save)
        filem.add_separator()
        filem.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filem)
        self.root.config(menu=menubar)

        tb = tk.Frame(self.root)
        tb.pack(fill=tk.X)
        tk.Label(tb, text="Font").pack(side=tk.LEFT)
        self.font_var = tk.StringVar(value=self.model.current_font_name)
        self.font_menu = tk.OptionMenu(tb, self.font_var, *self.model.font_manager.names())
        self.font_menu.pack(side=tk.LEFT)
        tk.Button(tb, text="Add Font", command=self.on_add_font).pack(side=tk.LEFT)

        tk.Label(tb, text="Size").pack(side=tk.LEFT)
        self.size_var = tk.IntVar(value=self.model.current_font_size)
        tk.OptionMenu(tb, self.size_var, *[8, 10, 12, 14, 16, 18, 20, 24, 32]).pack(side=tk.LEFT)

        btns = tk.Frame(self.root)
        btns.pack(fill=tk.X)
        for label, fn in [("Prev", self.on_prev), ("Next", self.on_next), ("Undo", self.on_undo), ("Redo", self.on_redo)]:
            tk.Button(btns, text=label, command=fn).pack(side=tk.LEFT)

        self.status = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status, anchor="w").pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas = tk.Canvas(self.root, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_add)
        self.canvas.bind("<Button-3>", self.on_select)
        self.canvas.bind("<B3-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_release)
        self.canvas.bind("<MouseWheel>", self.on_zoom)

    def render(self):
        self.canvas.delete("all")
        page = self.model.doc.load_page(self.model.page_index)
        self.model.page_width, self.model.page_height = page.rect.width, page.rect.height
        pix = page.get_pixmap(matrix=fitz.Matrix(self.model.scale, self.model.scale))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        draw = ImageDraw.Draw(img)

        for it in self.model.elements_by_page.get(self.model.page_index, []):
            x, y = it.coordinate.pdf_to_gui(self.model.scale, self.model.page_height, (0, 0))
            font = ImageFont.truetype(it.font_path, int(it.font_size * self.model.scale)) if it.font_path else ImageFont.load_default()
            draw.text((x, y), it.text, font=font, fill="black")

        self.tk_img = ImageTk.PhotoImage(img)
        ox, oy = self.controller.pan_offset
        self.canvas.create_image(ox, oy, image=self.tk_img, anchor="nw")

    def show_text_entry(self, x: int, y: int, font_name: str, font_size: int, on_commit):
        if self.entry:
            self.entry.destroy()
        self.entry = tk.Entry(self.canvas, font=(font_name, int(font_size * self.model.scale)))
        self.entry.place(x=x, y=y)
        self.entry.focus_set()

        def commit(_ev=None):
            if not self.entry:
                return
            txt = self.entry.get()
            self.entry.destroy()
            self.entry = None
            on_commit(txt)

        self.entry.bind("<Return>", commit)
        self.entry.bind("<FocusOut>", commit)

    def on_open(self): self.controller.open_pdf()
    def on_save(self): self.controller.save()
    def on_prev(self): self.controller.prev_page()
    def on_next(self): self.controller.next_page()
    def on_undo(self): self.controller.undo()
    def on_redo(self): self.controller.redo()
    def on_add(self, e): self.controller.add_text(e)
    def on_select(self, e): self.controller.select(e)
    def on_drag(self, e): self.controller.drag(e)
    def on_release(self, e): self.controller.release(e)
    def on_zoom(self, e): self.controller.zoom(e)

    def on_add_font(self):
        path = filedialog.askopenfilename(filetypes=[("Font", "*.ttf *.otf")])
        if not path:
            return
        name = self.model.font_manager.add_font(path)
        self.font_menu["menu"].add_command(label=name, command=tk._setit(self.font_var, name))
        self.font_var.set(name)
        self.status.set(f"フォント追加: {name}")


class PDFController:
    def __init__(self, model: PDFModel, view: PDFView):
        self.model = model
        self.view = view
        self.view.controller = self
        self.pan_offset = [0.0, 0.0]
        self.pan_start = (0.0, 0.0)
        self.panning = False
        self.drag_before: TextElement | None = None
        self.view.render()

    def add_text(self, e):
        coord = Coordinate.gui_to_pdf(e.x, e.y, self.model.scale, self.model.page_height, tuple(self.pan_offset))
        font_name = self.view.font_var.get()
        font_size = self.view.size_var.get()

        if self.model.font_manager.path_of(font_name) is None:
            messagebox.showwarning("フォント警告", "日本語文字化け防止のため TTF/OTF フォントを選択してください。")

        def on_commit(text: str):
            if text:
                self.model.add_text(coord, text, font_name, font_size)
                self.view.render()

        self.view.show_text_entry(e.x, e.y, font_name, font_size, on_commit)

    def select(self, e):
        self.model.drag_item = None
        for item in self.model.elements_by_page.get(self.model.page_index, []):
            x, y = item.coordinate.pdf_to_gui(self.model.scale, self.model.page_height, tuple(self.pan_offset))
            font = ImageFont.truetype(item.font_path, int(item.font_size * self.model.scale)) if item.font_path else ImageFont.load_default()
            w = font.getlength(item.text) if hasattr(font, "getlength") else font.getsize(item.text)[0]
            h = sum(font.getmetrics())
            if x <= e.x <= x + w and y <= e.y <= y + h:
                self.model.drag_item = item
                self.drag_before = replace(item)
                self.model.drag_offset = (e.x - x, e.y - y)
                return
        self.panning = True
        self.pan_start = (e.x, e.y)

    def drag(self, e):
        if self.model.drag_item:
            nx = e.x - self.model.drag_offset[0]
            ny = e.y - self.model.drag_offset[1]
            self.model.drag_item.coordinate = Coordinate.gui_to_pdf(nx, ny, self.model.scale, self.model.page_height, tuple(self.pan_offset))
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
            self.model.apply_operation(MoveTextOperation(self.drag_before, after))
            self.model.drag_item = None
            self.drag_before = None
        self.panning = False

    def save(self):
        out = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not out:
            return
        ok, msg = self.model.save_pdf(out)
        self.view.status.set(msg)
        if ok:
            self.model.doc = fitz.open(out)
            self.model.path = out
            self.view.render()

    def open_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        self.model.__init__(path)
        self.view.font_var.set(self.model.current_font_name)
        self.pan_offset = [0.0, 0.0]
        self.view.render()

    def undo(self): self.model.undo(); self.view.render()
    def redo(self): self.model.redo(); self.view.render()
    def next_page(self):
        if self.model.page_index < len(self.model.doc) - 1:
            self.model.page_index += 1
            self.view.render()

    def prev_page(self):
        if self.model.page_index > 0:
            self.model.page_index -= 1
            self.view.render()

    def zoom(self, e):
        self.model.scale *= 1.2 if e.delta > 0 else 1 / 1.2
        self.view.render()


def main():
    root = tk.Tk()
    root.withdraw()
    pdf_path = sys.argv[1] if len(sys.argv) >= 2 else filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
    if not pdf_path:
        print("No file selected.")
        sys.exit(0)
    root.deiconify()
    model = PDFModel(pdf_path)
    view = PDFView(root, model)
    PDFController(model, view)
    root.mainloop()


if __name__ == "__main__":
    main()
