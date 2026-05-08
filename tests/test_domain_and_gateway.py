import pytest
fitz = pytest.importorskip("fitz")

from pdf_text_studio.domain.models import Coordinate, TextElement, Document, AddTextOperation, MoveTextOperation, DeleteTextOperation, EditTextOperation
from pdf_text_studio.infrastructure.pdf_gateway import PDFGateway
from pdf_text_studio.app.editor import EditorApplication


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


def test_edit_text_operation_execute_undo():
    doc = Document()
    before = TextElement(1, 0, "old", Coordinate(100, 500), 12, "Noto", "/tmp/font.ttf")
    AddTextOperation(before).execute(doc)
    after = TextElement(1, 0, "new", Coordinate(120, 520), 18, "Noto2", "/tmp/font2.ttf")

    op = EditTextOperation(before, after)
    op.execute(doc)
    edited = doc.find_element(0, 1)
    assert edited.text == "new"
    assert edited.coordinate == Coordinate(120, 520)
    assert edited.font_size == 18
    assert edited.font_name == "Noto2"

    op.undo(doc)
    restored = doc.find_element(0, 1)
    assert restored.text == "old"
    assert restored.coordinate == Coordinate(100, 500)
    assert restored.font_size == 12
    assert restored.font_name == "Noto"


def test_create_empty_document_has_single_page():
    gateway = PDFGateway()
    doc = gateway.create_empty_document()
    try:
        assert len(doc) == 1
    finally:
        doc.close()


def test_editor_can_boot_without_source_and_save(tmp_path):
    app = EditorApplication()
    out = tmp_path / "empty_saved.pdf"
    ok, msg = app.save(str(out))
    app.shutdown()
    assert ok is True
    assert "保存" in msg
    assert out.exists()
