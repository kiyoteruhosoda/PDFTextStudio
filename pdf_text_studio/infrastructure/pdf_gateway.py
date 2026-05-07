from __future__ import annotations

import fitz

from pdf_text_studio.domain.models import TextElement


class PDFGateway:
    def open(self, path: str) -> fitz.Document:
        return fitz.open(path)

    def save_with_elements(self, source_path: str, out_path: str, elements_by_page: dict[int, list[TextElement]]) -> tuple[bool, str]:
        if source_path == out_path:
            return False, "元PDFへの上書きは禁止です。別名保存してください。"

        out_doc = fitz.open(source_path)
        for page_idx, elements in elements_by_page.items():
            page = out_doc.load_page(page_idx)
            for el in elements:
                if not el.font_path:
                    out_doc.close()
                    return False, f"フォント未設定: {el.font_name}。日本語フォントを選択してください。"
                page.insert_text((el.coordinate.x_pt, el.coordinate.y_pt), el.text, fontsize=el.font_size, fontfile=el.font_path, overlay=True)
        out_doc.save(out_path)
        out_doc.close()
        return True, "保存しました。"
