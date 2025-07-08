"""
PDF Editor
----------
- PDFModel: PDFデータ・状態管理（モデル）
- PDFView: 画面表示・UI操作（ビュー）
- PDFController: ユーザー操作の制御（コントローラ）
"""

import os
import sys
import io
import fitz
import tkinter as tk
from tkinter import filedialog, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

VERSION = 0.33

# --- Model: PDFの状態・データ管理 ---
class PDFModel:
    """PDFの状態・編集データを管理するクラス"""
    def __init__(self, path):
        self.path = path
        self.doc = fitz.open(path)
        self.page_index = 0
        self.page_width, self.page_height = self._get_size(0)
        self.scale = 1.5
        self.text_items = {}
        self.undo_stack = []
        self.redo_stack = []
        self.fonts = []
        self.default_font_file, self.default_font_name = self._init_default_font()
        self.fonts.append((self.default_font_name, self.default_font_file))
        self.current_font_name = self.default_font_name
        self.current_font_size = 16
        self.drag_item = None
        self.drag_offset = (0, 0)

    def _init_default_font(self):
        cwd = os.getcwd()
        ttfs = [f for f in os.listdir(cwd) if f.lower().endswith('.ttf')]
        if ttfs:
            path = os.path.join(cwd, ttfs[0])
            name = os.path.splitext(ttfs[0])[0]
            pdfmetrics.registerFont(TTFont(name, path))
            return path, name
        pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
        return None, 'HeiseiMin-W3'

    def _get_size(self, idx):
        r = self.doc.load_page(idx).rect
        return r.width, r.height

    def add_text(self, x, y, text, fs, font_name):
        font_file = next((f for n, f in self.fonts if n == font_name), None)
        item = dict(x=x, y=y, text=text, fs=fs, font_file=font_file, font_name=font_name)
        self.text_items.setdefault(self.page_index, []).append(item)
        self.undo_stack.append(('add', self.page_index, item))
        self.redo_stack.clear()

    def move_text(self, item, nx, ny):
        old = (item['x'], item['y'])
        item['x'], item['y'] = nx, ny
        self.undo_stack.append(('move', self.page_index, item, old))
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return
        action = self.undo_stack.pop()
        kind, pg, item = action[0], action[1], action[2]
        if kind == 'add':
            self.text_items[pg].remove(item)
        else:
            old = action[3]
            item['x'], item['y'] = old
        self.redo_stack.append(action)

    def redo(self):
        if not self.redo_stack:
            return
        action = self.redo_stack.pop()
        kind, pg, item = action[0], action[1], action[2]
        if kind == 'add':
            self.text_items.setdefault(pg, []).append(item)
        elif kind == 'move':
            new = action[3]
            item['x'], item['y'] = new
        self.undo_stack.append(action)

    def next_page(self):
        if self.page_index < len(self.doc) - 1:
            self.page_index += 1

    def prev_page(self):
        if self.page_index > 0:
            self.page_index -= 1

    def save_pdf(self, out_path):
        w, h = self._get_size(0)
        c = rl_canvas.Canvas(out_path, pagesize=(w, h))
        for pi in range(len(self.doc)):
            pix = self.doc.load_page(pi).get_pixmap(dpi=150)
            c.drawImage(ImageReader(io.BytesIO(pix.tobytes('png'))), 0, 0, width=w, height=h)
            for it in self.text_items.get(pi, []):
                c.setFont(it['font_name'], it['fs'])
                face = pdfmetrics.getFont(it['font_name']).face
                asc = face.ascent / 1000 * it['fs']
                y_pdf = it['y']
                c.drawString(it['x'], y_pdf - asc, it['text'])
            c.showPage()
        c.save()

# --- View: UI・画面表示 ---
class PDFView:
    """TkinterベースのUI・画面描画クラス"""
    def __init__(self, root, model):
        self.root = root
        self.model = model
        self.entry = None
        self._build_ui()

    def _build_ui(self):
        self.root.title(f"PDF Editor v{VERSION}")
        self.root.geometry('750x750')
        self.root.configure(bg='#f4f4f4')

        # メニューバー
        menubar = tk.Menu(self.root)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label='Open', command=self.on_open)
        filem.add_command(label='Save', command=self.on_save)
        filem.add_separator()
        filem.add_command(label='Exit', command=self.root.quit)
        menubar.add_cascade(label='File', menu=filem)
        self.root.config(menu=menubar)

        # ツールバー
        tb = tk.Frame(self.root, bg='#e0e0e0', pady=8)
        tb.pack(fill=tk.X, padx=0, pady=(0, 2))

        tk.Label(tb, text='Font:', bg='#e0e0e0').pack(side=tk.LEFT, padx=(10, 2))
        self.font_var = tk.StringVar(value=self.model.current_font_name)
        self.font_menu = tk.OptionMenu(tb, self.font_var, *[n for n, _ in self.model.fonts])
        self.font_menu.config(bg='white', relief=tk.FLAT)
        self.font_menu.pack(side=tk.LEFT, padx=2)
        tk.Button(tb, text='Add Font', command=self.on_add_font, bg='#1976d2', fg='white', relief=tk.FLAT).pack(side=tk.LEFT, padx=8)
        tk.Label(tb, text='Size:', bg='#e0e0e0').pack(side=tk.LEFT, padx=(10, 2))
        sizes = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 72]
        self.size_var = tk.IntVar(value=self.model.current_font_size)
        self.size_menu = tk.OptionMenu(tb, self.size_var, *sizes)
        self.size_menu.config(bg='white', relief=tk.FLAT)
        self.size_menu.pack(side=tk.LEFT, padx=2)

        # 操作ボタン
        ctrl = tk.Frame(self.root, bg='#f4f4f4')
        ctrl.pack(fill=tk.X, padx=0, pady=(0, 8))
        btn_style = dict(bg='#1976d2', fg='white', relief=tk.FLAT, font=('Segoe UI', 10, 'bold'), padx=10, pady=4)
        for txt, cmd in [('Prev', self.on_prev), ('Next', self.on_next), ('Undo', self.on_undo), ('Redo', self.on_redo)]:
            tk.Button(ctrl, text=txt, command=cmd, **btn_style).pack(side=tk.LEFT, padx=6)

        # ステータスバー
        self.status = tk.StringVar()
        statusbar = tk.Label(self.root, textvariable=self.status, anchor='w', bg='#eeeeee', fg='#333', font=('Segoe UI', 9))
        statusbar.pack(fill=tk.X, side=tk.BOTTOM, ipady=2)

        # キャンバス
        self.canvas = tk.Canvas(self.root, bg='white', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        self.canvas.bind('<Button-1>', self.on_add)
        self.canvas.bind('<MouseWheel>', self.on_zoom)
        self.canvas.bind('<Button-3>', self.on_select)
        self.canvas.bind('<B3-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-3>', self.on_release)

    def render(self):
        self.canvas.delete('all')
        p = self.model.doc.load_page(self.model.page_index)
        pix = p.get_pixmap(matrix=fitz.Matrix(self.model.scale, self.model.scale))
        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        draw = ImageDraw.Draw(img)
        for it in self.model.text_items.get(self.model.page_index, []):
            x = it['x'] * self.model.scale
            y = (self.model.page_height - it['y']) * self.model.scale
            font = ImageFont.truetype(it['font_file'], int(it['fs'] * self.model.scale)) if it['font_file'] else ImageFont.load_default()
            draw.text((x, y), it['text'], font=font, fill='black')
            if it is self.model.drag_item:
                if hasattr(draw, "textbbox"):
                    bb = draw.textbbox((x, y), it['text'], font=font)
                else:
                    width, height = font.getsize(it['text'])
                    bb = (x, y, x + width, y + height)
                draw.rectangle(bb, outline='blue', width=2)
        self.tk_img = ImageTk.PhotoImage(img)
        offset_x, offset_y = getattr(self.controller, 'pan_offset', [0, 0])
        self.canvas.create_image(offset_x, offset_y, image=self.tk_img, anchor='nw')
        w_scaled = self.model.page_width * self.model.scale
        h_scaled = self.model.page_height * self.model.scale
        self.canvas.create_rectangle(offset_x, offset_y, w_scaled + offset_x, h_scaled + offset_y, outline='red', width=2)

    # --- UIイベント ---
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
        path = filedialog.askopenfilename(filetypes=[('TTF', '*.ttf')])
        if not path:
            return
        name = os.path.splitext(os.path.basename(path))[0]
        if any(n == name for n, _ in self.model.fonts):
            self.status.set(f'Font "{name}" is already added.')
            return
        pdfmetrics.registerFont(TTFont(name, path))
        self.model.fonts.append((name, path))
        self.font_menu['menu'].add_command(label=name, command=tk._setit(self.font_var, name))
        self.font_var.set(name)
        self.status.set(f'Font added: {name}')

    def show_text_entry(self, x_canvas, y_canvas, font_name, font_size, on_commit):
        if hasattr(self, 'entry') and self.entry:
            self.entry.destroy()
        scaled_font_size = int(font_size * self.model.scale)
        self.entry = tk.Entry(self.canvas, font=(font_name, scaled_font_size), insertbackground='black')
        self.entry.place(x=x_canvas, y=y_canvas)
        self.entry.focus_set()
        self.entry.config(cursor='xterm')
        def commit(event=None):
            text = self.entry.get()
            self.entry.destroy()
            self.entry = None
            on_commit(text)
        self.entry.bind('<Return>', commit)
        self.entry.bind('<FocusOut>', lambda e: commit())

    def on_open(self):
        path = filedialog.askopenfilename(filetypes=[('PDF', '*.pdf')])
        if not path:
            return
        self.model.__init__(path)
        self.font_var.set(self.model.current_font_name)
        self.size_var.set(self.model.current_font_size)
        self.render()
        self.status.set(f'Opened: {os.path.basename(path)}')

# --- Controller: ユーザー操作の制御 ---
class PDFController:
    """ユーザー操作をモデル・ビューに橋渡しするクラス"""
    def __init__(self, model, view):
        self.model = model
        self.view = view
        view.controller = self
        view.render()
        self.panning = False
        self.pan_start = (0, 0)
        self.pan_offset = [0, 0]

    def add_text(self, e):
        rx = self.view.canvas.canvasx(e.x)
        ry = self.view.canvas.canvasy(e.y)
        offset_x, offset_y = self.pan_offset
        x_pdf = (rx - offset_x) / self.model.scale
        y_pdf = self.model.page_height - (ry - offset_y) / self.model.scale
        font_name = self.view.font_var.get()
        font_size = self.view.size_var.get()
        def on_commit(txt):
            if txt:
                self.model.add_text(x_pdf, y_pdf, txt, font_size, font_name)
                self.view.render()
        self.view.show_text_entry(rx, ry, font_name, font_size, on_commit)

    def select(self, e):
        rx = self.view.canvas.canvasx(e.x)
        ry = self.view.canvas.canvasy(e.y)
        offset_x, offset_y = self.pan_offset
        self.model.drag_item = None
        for it in self.model.text_items.get(self.model.page_index, []):
            font = ImageFont.truetype(it['font_file'], int(it['fs'] * self.model.scale)) if it['font_file'] else ImageFont.load_default()
            asc, des = font.getmetrics()
            height = asc + des
            width = font.getlength(it['text']) if hasattr(font, 'getlength') else font.getsize(it['text'])[0]
            x = it['x'] * self.model.scale + offset_x
            y = (self.model.page_height - it['y']) * self.model.scale + offset_y
            if x <= rx <= x + width and y <= ry <= y + height:
                self.model.drag_item = it
                self.model.drag_offset = (rx - x, ry - y)
                self.panning = False
                break
        else:
            self.panning = True
            self.pan_start = (rx, ry)
        self.view.render()

    def drag(self, e):
        rx = self.view.canvas.canvasx(e.x)
        ry = self.view.canvas.canvasy(e.y)
        offset_x, offset_y = self.pan_offset
        if self.model.drag_item:
            nx = (rx - self.model.drag_offset[0] - offset_x) / self.model.scale
            ny = self.model.page_height - (ry - self.model.drag_offset[1] - offset_y) / self.model.scale
            self.model.move_text(self.model.drag_item, nx, ny)
            self.view.render()
        elif self.panning:
            dx = rx - self.pan_start[0]
            dy = ry - self.pan_start[1]
            self.pan_offset[0] += dx
            self.pan_offset[1] += dy
            self.pan_start = (rx, ry)
            self.view.render()

    def release(self, e):
        if self.model.drag_item:
            rx = self.view.canvas.canvasx(e.x)
            ry = self.view.canvas.canvasy(e.y)
            offset_x, offset_y = self.pan_offset
            nx = (rx - self.model.drag_offset[0] - offset_x) / self.model.scale
            ny = self.model.page_height - (ry - self.model.drag_offset[1] - offset_y) / self.model.scale
            self.model.move_text(self.model.drag_item, nx, ny)
            self.model.drag_item = None
        self.panning = False
        self.view.render()

    def save(self):
        path = filedialog.asksaveasfilename(defaultextension='.pdf')
        if not path:
            return
        if os.path.abspath(path) == os.path.abspath(self.model.path):
            self.view.status.set('Cannot overwrite the file currently open. Please choose another name.')
            return
        self.model.save_pdf(path)
        self.view.status.set('Saved')
        self.view.render()

    def redo(self):
        self.model.redo()
        self.view.render()

    def undo(self):
        self.model.undo()
        self.view.render()

    def next(self):
        self.model.next_page()
        self.view.render()

    def prev(self):
        self.model.prev_page()
        self.view.render()

    def zoom(self, e):
        self.model.scale *= 1.2 if e.delta > 0 else 1 / 1.2
        self.view.render()

# --- アプリ起動 ---
def main():
    r = tk.Tk()
    r.withdraw()
    if len(sys.argv) >= 2:
        pdf_path = sys.argv[1]
    else:
        pdf_path = filedialog.askopenfilename(filetypes=[('PDF', '*.pdf')])
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
