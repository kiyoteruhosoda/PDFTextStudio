import fitz

from pdf_text_studio.domain.models import Coordinate, TextElement, Document, AddTextOperation, MoveTextOperation, DeleteTextOperation
from pdf_text_studio.infrastructure.pdf_gateway import PDFGateway


def test_coordinate_roundtrip_baseline():
    c = Coordinate.gui_to_pdf_baseline(300, 200, 2.0, 800, (10, 20), 24)
    x, y = c.pdf_baseline_to_gui_top(2.0, 800, (10, 20), 24)
    assert abs(x - 300) < 1e-6
    assert abs(y - 200) < 1e-6


def _element():
    return TextElement(1, 0, "abc", Coordinate(100, 500), 12, "Noto", "/tmp/font.ttf")


def test_add_move_delete_operations():
    doc = Document()
    e = _element()
    add = AddTextOperation(e)
    add.execute(doc)
    assert doc.find_element(0, 1) is not None
    add.undo(doc)
    assert doc.find_element(0, 1) is None

    add.execute(doc)
    moved = TextElement(1, 0, "abc", Coordinate(120, 530), 12, "Noto", "/tmp/font.ttf")
    mv = MoveTextOperation(e, moved)
    mv.execute(doc)
    assert doc.find_element(0, 1).coordinate == Coordinate(120, 530)
    mv.undo(doc)
    assert doc.find_element(0, 1).coordinate == Coordinate(100, 500)

    delete = DeleteTextOperation(e)
    delete.execute(doc)
    assert doc.find_element(0, 1) is None
    delete.undo(doc)
    assert doc.find_element(0, 1) is not None


def test_save_reject_overwrite(tmp_path):
    src = tmp_path / "a.pdf"
    doc = fitz.open(); doc.new_page(); doc.save(src); doc.close()
    gateway = PDFGateway()
    ok, msg = gateway.save_with_elements(str(src), str(src), {})
    assert ok is False
    assert "上書き" in msg
