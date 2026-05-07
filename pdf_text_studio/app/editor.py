from __future__ import annotations

import os
from dataclasses import replace

from pdf_text_studio.domain.models import (
    Document, Coordinate, TextElement, EditOperation,
    AddTextOperation, MoveTextOperation, DeleteTextOperation, EditTextOperation
)
from pdf_text_studio.infrastructure.font_manager import FontManager
from pdf_text_studio.infrastructure.pdf_gateway import PDFGateway


class EditorApplication:
    def __init__(self, pdf_path: str):
        self.gateway = PDFGateway()
        self.font_manager = FontManager()
        self.source_path = pdf_path
        self.doc = self.gateway.open(pdf_path)
        self.preview_doc = None
        self.preview_temp_path: str | None = None
        self.is_preview_mode = False
        self.page_index = 0
        rect = self.doc.load_page(0).rect
        self.page_width, self.page_height = rect.width, rect.height
        self.scale = 1.5
        self.document = Document()
        self.undo_stack: list[EditOperation] = []
        self.redo_stack: list[EditOperation] = []
        self.current_font_name = self.font_manager.names()[0]
        self.current_font_size = 16
        self.drag_item: TextElement | None = None
        self.drag_offset = (0.0, 0.0)
        self._id_seq = 1

    @property
    def elements_by_page(self): return self.document.elements_by_page

    def apply_operation(self, op: EditOperation, record_history: bool = True):
        op.execute(self.document)
        if record_history:
            self.undo_stack.append(op)
            self.redo_stack.clear()

    def add_text(self, coord: Coordinate, text: str, font_name: str, font_size: float):
        el = TextElement(self._id_seq, self.page_index, text, coord, font_size, font_name, self.font_manager.path_of(font_name))
        self._id_seq += 1
        self.apply_operation(AddTextOperation(el))

    def move_text(self, before: TextElement, after: TextElement): self.apply_operation(MoveTextOperation(before, after))
    def delete_text(self, element: TextElement): self.apply_operation(DeleteTextOperation(replace(element)))
    def edit_text(self, before: TextElement, after: TextElement): self.apply_operation(EditTextOperation(before, after))

    def save(self, out_path: str) -> tuple[bool, str]:
        if os.path.abspath(out_path) == os.path.abspath(self.source_path):
            return False, "元PDFへの上書きは禁止です。別名保存してください。"
        return self.gateway.save_with_elements(self.source_path, out_path, self.document.elements_by_page)

    def create_preview(self) -> tuple[bool, str, str | None]:
        self.cleanup_preview()
        return self.gateway.preview_with_tempfile(self.source_path, self.document.elements_by_page)

    def load_preview(self, preview_path: str):
        self.cleanup_preview(close_only=True)
        self.preview_temp_path = preview_path
        self.preview_doc = self.gateway.open(preview_path)
        self.doc = self.preview_doc
        self.is_preview_mode = True

    def load_source(self):
        self.cleanup_preview(close_only=True)
        self.doc = self.gateway.open(self.source_path)
        self.is_preview_mode = False

    def cleanup_preview(self, close_only: bool = False):
        if self.preview_doc is not None:
            self.preview_doc.close()
            self.preview_doc = None
        if (not close_only) and self.preview_temp_path and os.path.exists(self.preview_temp_path):
            os.remove(self.preview_temp_path)
            self.preview_temp_path = None

    def shutdown(self):
        self.cleanup_preview()
        if self.doc is not None:
            self.doc.close()

    def undo(self):
        if self.undo_stack:
            op = self.undo_stack.pop(); op.undo(self.document); self.redo_stack.append(op)

    def redo(self):
        if self.redo_stack:
            op = self.redo_stack.pop(); op.execute(self.document); self.undo_stack.append(op)
