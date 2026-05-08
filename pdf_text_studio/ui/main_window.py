from __future__ import annotations

from dataclasses import replace

import fitz
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QImage, QKeyEvent, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QToolBar,
    QWidget,
)

from pdf_text_studio.app.editor import EditorApplication
from pdf_text_studio.domain.models import Coordinate


class PdfGraphicsView(QGraphicsView):
    def __init__(self, window: "MainWindow", scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.window = window
        self.setRenderHint(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = self.mapToScene(event.pos())
        if event.button() == Qt.MouseButton.LeftButton:
            self.window.on_add(pos)
        elif event.button() == Qt.MouseButton.RightButton:
            self.window.on_select(pos)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.RightButton:
            self.window.on_drag(self.mapToScene(event.pos()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.window.on_release()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.window.on_double_click(self.mapToScene(event.pos()))
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.window.on_zoom(event.angleDelta().y())
            return
        super().wheelEvent(event)

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
        self.scene = QGraphicsScene(self)
        self.pdf_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pdf_item)
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
        self.resize(1200, 800)

        file_menu = self.menuBar().addMenu("File")
        for title, handler in [("Open", self.open_pdf), ("Save", self.save_pdf)]:
            action = QAction(title, self)
            action.triggered.connect(handler)
            file_menu.addAction(action)

        toolbar = QToolBar("Main Actions", self)
        self.addToolBar(toolbar)
        for title, handler in [
            ("Prev", self.prev_page),
            ("Next", self.next_page),
            ("Undo", self.undo),
            ("Redo", self.redo),
            ("Preview Export", self.preview_export),
            ("Back to Edit", self.back_to_edit),
            ("Add Font", self.add_font),
        ]:
            action = QAction(title, self)
            action.triggered.connect(handler)
            toolbar.addAction(action)

        sidebar = QDockWidget("Inspector", self)
        sidebar.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        side_content = QWidget()
        form = QFormLayout(side_content)

        self.font_combo = QComboBox()
        self.font_combo.addItems(self.app.font_manager.names())
        self.font_combo.setCurrentText(self.app.current_font_name)
        self.size_combo = QComboBox()
        for size in [8, 10, 12, 14, 16, 18, 20, 24, 32]:
            self.size_combo.addItem(str(size), size)
        self.size_combo.setCurrentText(str(self.app.current_font_size))
        self.page_label = QLabel()
        self.zoom_label = QLabel()
        self.mode_label = QLabel()
        self.status_label = QLabel()

        form.addRow("Font", self.font_combo)
        form.addRow("Size", self.size_combo)
        form.addRow("Page", self.page_label)
        form.addRow("Zoom", self.zoom_label)
        form.addRow("Mode", self.mode_label)
        form.addRow("Status", self.status_label)
        side_content.setFixedWidth(260)
        sidebar.setWidget(side_content)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, sidebar)

        self.view = PdfGraphicsView(self, self.scene)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.view)
        self.setCentralWidget(self.scroll_area)

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
        self.pdf_item.setPixmap(QPixmap.fromImage(qimage.copy()))
        self.scene.setSceneRect(self.pdf_item.boundingRect())
        self.page_label.setText(f"{self.app.page_index + 1} / {len(self.app.doc)}")
        self.zoom_label.setText(f"{self.app.scale * 100:.0f}%")
        self.mode_label.setText("Preview" if self.app.is_preview_mode else "Edit")
        if not self.status_label.text():
            self.status_label.setText("Ready")

    def _find_hit(self, p: QPointF):
        for item in reversed(self.app.elements_by_page.get(self.app.page_index, [])):
            font = self._font(item)
            asc, des = font.getmetrics()
            w = font.getlength(item.text) if hasattr(font, "getlength") else font.getsize(item.text)[0]
            x, y_top = item.coordinate.pdf_baseline_to_gui_top(self.app.scale, self.app.page_height, tuple(self.pan_offset), asc)
            if x <= p.x() <= x + w and y_top <= p.y() <= y_top + asc + des:
                return item, x, y_top
        return None, 0, 0

    def on_add(self, p: QPointF):
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
        self.show_entry(int(p.x()), int(p.y()), lambda txt: self._commit_add(txt, coord, font_name))

    def _commit_add(self, txt, coord, font_name):
        if txt:
            self.app.add_text(coord, txt, font_name, self._size_value())
            self.render()

    def on_select(self, p: QPointF):
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

    def on_drag(self, p: QPointF):
        if not self._editable():
            return
        if self.app.drag_item:
            font = self._font(self.app.drag_item)
            asc, _ = font.getmetrics()
            nx, ny = p.x() - self.app.drag_offset[0], p.y() - self.app.drag_offset[1]
            self.app.drag_item.coordinate = Coordinate.gui_to_pdf_baseline(nx, ny, self.app.scale, self.app.page_height, tuple(self.pan_offset), asc)
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

    def on_double_click(self, p: QPointF):
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
            self.app.undo(); self.render()

    def redo(self):
        if self._editable():
            self.app.redo(); self.render()

    def next_page(self):
        if self.app.page_index < len(self.app.doc) - 1:
            self.app.page_index += 1; self.render()

    def prev_page(self):
        if self.app.page_index > 0:
            self.app.page_index -= 1; self.render()

    def preview_export(self):
        ok, msg, path = self.app.create_preview(); self.status_label.setText(msg)
        if ok and path:
            self.app.load_preview(path); self.render()

    def save_pdf(self):
        if self.app.is_preview_mode:
            self.status_label.setText("Preview中は保存できません。Back to Edit で戻ってから保存してください。")
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save PDF", filter="PDF (*.pdf)")
        if not out:
            return
        _, msg = self.app.save(out); self.status_label.setText(msg)

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", filter="PDF (*.pdf)")
        if not path:
            return
        self._clear_interaction_state(); self.app.cleanup_preview(); self.app.__init__(path)
        self.font_combo.setCurrentText(self.app.current_font_name)
        self.pan_offset = [0.0, 0.0]
        self.status_label.setText("Ready")
        self.render()

    def back_to_edit(self):
        self._clear_interaction_state(); self.app.load_source(); self.render()

    def _clear_interaction_state(self):
        self.selected_item = None; self.app.drag_item = None; self.drag_before = None; self.panning = False

    def add_font(self):
        path, _ = QFileDialog.getOpenFileName(self, "Add Font", filter="Fonts (*.ttf *.otf)")
        if not path:
            return
        name = self.app.font_manager.add_font(path); self.font_combo.addItem(name); self.font_combo.setCurrentText(name)

    def show_entry(self, x: int, y: int, on_commit):
        if self.entry:
            self.entry.deleteLater()
        self.entry = QLineEdit(self.view.viewport())
        self.entry.move(x, y)
        self.entry.returnPressed.connect(lambda: self._commit_entry(on_commit))
        self.entry.editingFinished.connect(lambda: self._commit_entry(on_commit))
        self.entry.show(); self.entry.setFocus()

    def _commit_entry(self, on_commit):
        if not self.entry:
            return
        text = self.entry.text(); self.entry.deleteLater(); self.entry = None; on_commit(text)
