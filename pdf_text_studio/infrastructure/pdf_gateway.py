from __future__ import annotations

import os
import tempfile

import fitz

from pdf_text_studio.domain.models import TextElement


class PDFGateway:
    def open(self, path: str) -> fitz.Document:
        return fitz.open(path)

    def _write_elements(self, out_doc: fitz.Document, elements_by_page: dict[int, list[TextElement]]) -> tuple[bool, str]:
        for page_idx, elements in elements_by_page.items():
            page = out_doc.load_page(page_idx)
            for el in elements:
                if not el.font_path:
                    return False, "TTF/OTFフォントを選択してください"
                font_name = f"f_{el.font_name}_{page_idx}_{el.element_id}".replace(" ", "_")
                page.insert_text((el.coordinate.x_pt, el.coordinate.y_pt), el.text, fontsize=el.font_size, fontfile=el.font_path, fontname=font_name, overlay=True)
        return True, "ok"

    def save_with_elements(self, source_path: str, out_path: str, elements_by_page: dict[int, list[TextElement]]) -> tuple[bool, str]:
        if os.path.abspath(source_path) == os.path.abspath(out_path):
            return False, "元PDFへの上書きは禁止です。別名保存してください。"
        out_doc = fitz.open(source_path)
        ok, msg = self._write_elements(out_doc, elements_by_page)
        if not ok:
            out_doc.close(); return False, msg
        out_doc.save(out_path)
        out_doc.close()
        return True, "保存しました。"

    def preview_with_tempfile(self, source_path: str, elements_by_page: dict[int, list[TextElement]]) -> tuple[bool, str, str | None]:
        out_doc = fitz.open(source_path)
        ok, msg = self._write_elements(out_doc, elements_by_page)
        if not ok:
            out_doc.close(); return False, msg, None
        fd, temp_path = tempfile.mkstemp(suffix='.pdf', prefix='pdftextstudio_preview_')
        os.close(fd)
        out_doc.save(temp_path)
        out_doc.close()
        return True, "プレビューを生成しました。", temp_path
