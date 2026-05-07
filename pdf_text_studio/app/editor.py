from __future__ import annotations

import os
from dataclasses import replace

from pdf_text_studio.domain.models import Document, Coordinate, TextElement, EditOperation, AddTextOperation, MoveTextOperation
from pdf_text_studio.infrastructure.font_manager import FontManager
from pdf_text_studio.infrastructure.pdf_gateway import PDFGateway


class EditorApplication:
    def __init__(self, pdf_path: str):
        self.gateway = PDFGateway()
        self.font_manager = FontManager()
        self.path = pdf_path
        self.doc = self.gateway.open(pdf_path)
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
    def elements_by_page(self):
        return self.document.elements_by_page

    def apply_operation(self, op: EditOperation, record_history: bool = True):
        op.execute(self.document)
        if record_history:
            self.undo_stack.append(op)
            self.redo_stack.clear()

    def add_text(self, coord: Coordinate, text: str, font_name: str, font_size: float):
        element = TextElement(self._id_seq, self.page_index, text, coord, font_size, font_name, self.font_manager.path_of(font_name))
        self._id_seq += 1
        self.apply_operation(AddTextOperation(element))

    def move_text(self, before: TextElement, after: TextElement):
        self.apply_operation(MoveTextOperation(before, after))

    def preview_saved_pdf(self, out_path: str):
        self.doc = self.gateway.open(out_path)
        self.path = out_path

    def save(self, out_path: str) -> tuple[bool, str]:
        if os.path.abspath(out_path) == os.path.abspath(self.path):
            return False, "元PDFへの上書きは禁止です。別名保存してください。"
        return self.gateway.save_with_elements(self.path, out_path, self.document.elements_by_page)

    def undo(self):
        if not self.undo_stack:
            return
        op = self.undo_stack.pop()
        op.undo(self.document)
        self.redo_stack.append(op)

    def redo(self):
        if not self.redo_stack:
            return
        op = self.redo_stack.pop()
        op.execute(self.document)
        self.undo_stack.append(op)

    def clone_text_element(self, item: TextElement) -> TextElement:
        return replace(item)
