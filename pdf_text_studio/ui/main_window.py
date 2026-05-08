from __future__ import annotations

from dataclasses import replace

import fitz
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QImage, QKeyEvent, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QComboBox,
    QVBoxLayout,
    QWidget,
)

from pdf_text_studio.app.editor import EditorApplication
from pdf_text_studio.domain.models import Coordinate


class PdfCanvas(QLabel):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__()
        self.window = window
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.window.on_add(event.position().toPoint())
        elif event.button() == Qt.MouseButton.RightButton:
            self.window.on_select(event.position().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.RightButton:
            self.window.on_drag(event.position().toPoint())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.window.on_release()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.window.on_double_click(event.position().toPoint())

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.window.on_zoom(event.angleDelta().y())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            self.window.on_delete()
            return
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, app: EditorApplication, version: str):
        super().__init__()
        self.app, self.version = app, version
        self.entry: QLineEdit | None = None
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
            self.status_label.setText("Preview中は編集できません。Back to Editで戻ってください。")
            return False
        return True

    def _build_ui(self) -> None:
        self.setWindowTitle(f"PDFTextStudio v{self.version}")
        self.resize(760, 760)

        file_menu = self.menuBar().addMenu("File")
        open_action = QAction("Open", self)
        save_action = QAction("Save", self)
        open_action.triggered.connect(self.open_pdf)
        save_action.triggered.connect(self.save_pdf)
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        toolbar = QHBoxLayout()
        self.font_combo = QComboBox()
        self.font_combo.addItems(self.app.font_manager.names())
        self.font_combo.setCurrentText(self.app.current_font_name)
        self.size_combo = QComboBox()
        for size in [8, 10, 12, 14, 16, 18, 20, 24, 32]:
            self.size_combo.addItem(str(size), size)
        self.size_combo.setCurrentText(str(self.app.current_font_size))
        toolbar.addWidget(self.font_combo)
        add_font_button = QPushButton("Add Font")
        add_font_button.clicked.connect(self.add_font)
        toolbar.addWidget(add_font_button)
        toolbar.addWidget(self.size_combo)
        preview_button = QPushButton("Preview Export")
        preview_button.clicked.connect(self.preview_export)
        toolbar.addWidget(preview_button)
        back_button = QPushButton("Back to Edit")
        back_button.clicked.connect(self.back_to_edit)
        toolbar.addWidget(back_button)
        layout.addLayout(toolbar)

        ops = QHBoxLayout()
        for title, handler in [("Prev", self.prev_page), ("Next", self.next_page), ("Undo", self.undo), ("Redo", self.redo)]:
            button = QPushButton(title)
            button.clicked.connect(handler)
            ops.addWidget(button)
        layout.addLayout(ops)

        self.canvas = PdfCanvas(self)
        layout.addWidget(self.canvas, stretch=1)

        initial_status = "新規ドキュメントを開きました。File > Open からPDFを選択できます。" if self.app.source_path is None else "Ready"
        self.status_label = QLabel(initial_status)
        layout.addWidget(self.status_label)

    def _size_value(self) -> int:
        return int(self.size_combo.currentData() or int(self.size_combo.currentText()))

    def render(self) -> None:
        page = self.app.doc.load_page(self.app.page_index)
        self.app.page_width, self.app.page_height = page.rect.width, page.rect.height
        pix = page.get_pixmap(matrix=fitz.Matrix(self.app.scale, self.app.scale))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        draw = ImageDraw.Draw(img)
        if not self.app.is_preview_mode:
            for it in self.app.elements_by_page.get(self.app.page_index, []):
                font = self._font(it)
                asc, _ = font.getmetrics()
                x, y_top = it.coordinate.pdf_baseline_to_gui_top(self.app.scale, self.app.page_height, (0, 0), asc)
                draw.text((x, y_top), it.text, font=font, fill="black")

        qimage = QImage(img.tobytes("raw", "RGB"), img.width, img.height, QImage.Format.Format_RGB888)
        base = QPixmap.fromImage(qimage.copy())
        canvas_pixmap = QPixmap(base.width() + abs(int(self.pan_offset[0])) + 20, base.height() + abs(int(self.pan_offset[1])) + 20)
        canvas_pixmap.fill(Qt.GlobalColor.white)
        painter_pos = QPoint(max(0, int(self.pan_offset[0])), max(0, int(self.pan_offset[1])))
        from PySide6.QtGui import QPainter

        painter = QPainter(canvas_pixmap)
        painter.drawPixmap(painter_pos, base)
        painter.end()
        self.canvas.setPixmap(canvas_pixmap)
        self.canvas.adjustSize()
        self.canvas.setFocus()

    def _find_hit(self, p: QPoint):
        for item in reversed(self.app.elements_by_page.get(self.app.page_index, [])):
            font = self._font(item)
            asc, des = font.getmetrics()
            w = font.getlength(item.text) if hasattr(font, "getlength") else font.getsize(item.text)[0]
            x, y_top = item.coordinate.pdf_baseline_to_gui_top(self.app.scale, self.app.page_height, tuple(self.pan_offset), asc)
            if x <= p.x() <= x + w and y_top <= p.y() <= y_top + asc + des:
                return item, x, y_top
        return None, 0, 0

    def on_add(self, p: QPoint):
        if not self._editable() or self._find_hit(p)[0]:
            return
        font_name = self.font_combo.currentText()
        font_path = self.app.font_manager.path_of(font_name)
        if font_path is None:
            QMessageBox.critical(self, "フォントエラー", "TTF/OTFフォントを選択してください")
            return
        tmp_font = ImageFont.truetype(font_path, int(self._size_value() * self.app.scale))
        asc, _ = tmp_font.getmetrics()
        coord = Coordinate.gui_to_pdf_baseline(p.x(), p.y(), self.app.scale, self.app.page_height, tuple(self.pan_offset), asc)
        self.show_entry(p.x(), p.y(), font_name, self._size_value(), lambda txt: self._commit_add(txt, coord, font_name))

    def _commit_add(self, txt, coord, font_name):
        if txt:
            self.app.add_text(coord, txt, font_name, self._size_value())
            self.render()

    def on_select(self, p: QPoint):
        if not self._editable():
            return
        item, x, y_top = self._find_hit(p)
        self.app.drag_item = item
        self.selected_item = item
        if item:
            self.drag_before = replace(item)
            self.app.drag_offset = (p.x() - x, p.y() - y_top)
            self.panning = False
        else:
            self.panning = True
            self.pan_start = (p.x(), p.y())

    def on_drag(self, p: QPoint):
        if not self._editable():
            return
        if self.app.drag_item:
            font = self._font(self.app.drag_item)
            asc, _ = font.getmetrics()
            nx, ny = p.x() - self.app.drag_offset[0], p.y() - self.app.drag_offset[1]
            self.app.drag_item.coordinate = Coordinate.gui_to_pdf_baseline(nx, ny, self.app.scale, self.app.page_height, tuple(self.pan_offset), asc)
            self.render()
        elif self.panning:
            dx, dy = p.x() - self.pan_start[0], p.y() - self.pan_start[1]
            self.pan_offset[0] += dx
            self.pan_offset[1] += dy
            self.pan_start = (p.x(), p.y())
            self.render()

    def on_release(self):
        if self.app.drag_item and self.drag_before:
            self.app.move_text(self.drag_before, replace(self.app.drag_item))
        self.drag_before = None
        self.panning = False

    def on_delete(self):
        if self._editable() and self.selected_item:
            self.app.delete_text(self.selected_item)
            self.selected_item = None
            self.render()

    def on_double_click(self, p: QPoint):
        if not self._editable():
            return
        item, _, _ = self._find_hit(p)
        if not item:
            return
        new_text, ok = QInputDialog.getText(self, "Edit Text", "テキストを編集", text=item.text)
        if not ok:
            return
        before = replace(item)
        item.text = new_text
        item.font_size = float(self._size_value())
        item.font_name = self.font_combo.currentText()
        item.font_path = self.app.font_manager.path_of(item.font_name)
        self.app.edit_text(before, replace(item))
        self.render()

    def on_zoom(self, delta: int):
        self.app.scale *= 1.2 if delta > 0 else 1 / 1.2
        self.render()

    def undo(self):
        if self._editable():
            self.app.undo()
            self.render()

    def redo(self):
        if self._editable():
            self.app.redo()
            self.render()

    def next_page(self):
        if self.app.page_index < len(self.app.doc) - 1:
            self.app.page_index += 1
            self.render()

    def prev_page(self):
        if self.app.page_index > 0:
            self.app.page_index -= 1
            self.render()

    def preview_export(self):
        ok, msg, path = self.app.create_preview()
        self.status_label.setText(msg)
        if ok and path:
            self.app.load_preview(path)
            self.render()

    def save_pdf(self):
        if self.app.is_preview_mode:
            self.status_label.setText("Preview中は保存できません。Back to Edit で戻ってから保存してください。")
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save PDF", filter="PDF (*.pdf)")
        if not out:
            return
        _, msg = self.app.save(out)
        self.status_label.setText(msg)

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", filter="PDF (*.pdf)")
        if not path:
            return
        self._clear_interaction_state()
        self.app.cleanup_preview()
        self.app.__init__(path)
        self.font_combo.setCurrentText(self.app.current_font_name)
        self.pan_offset = [0.0, 0.0]
        self.render()

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
        path, _ = QFileDialog.getOpenFileName(self, "Add Font", filter="Fonts (*.ttf *.otf)")
        if not path:
            return
        name = self.app.font_manager.add_font(path)
        self.font_combo.addItem(name)
        self.font_combo.setCurrentText(name)

    def show_entry(self, x, y, _font_name, _font_size, on_commit):
        if self.entry:
            self.entry.deleteLater()
        self.entry = QLineEdit(self.canvas)
        self.entry.move(x, y)
        self.entry.returnPressed.connect(lambda: self._commit_entry(on_commit))
        self.entry.editingFinished.connect(lambda: self._commit_entry(on_commit))
        self.entry.show()
        self.entry.setFocus()

    def _commit_entry(self, on_commit):
        if not self.entry:
            return
        text = self.entry.text()
        self.entry.deleteLater()
        self.entry = None
        on_commit(text)
