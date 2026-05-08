# PDFTextStudio

**Version**: 43

日本語 PDF へのテキスト追記・移動・削除・編集・保存を、**PDFベースライン座標（pt）中心**で扱う GUI ツールです。

## 主な改善点

* 内部座標を **PDFベースライン座標** に統一
* `EditOperation` 抽象 + `Add/Move/Delete/Edit` のポリモーフィック Undo/Redo
* PySide6 (`QMainWindow` + `QToolBar` + `QDockWidget` + `QGraphicsView`) ベースのモダン UI
* `Preview Export` ボタンで一時PDFを生成し、保存前に見た目確認
* 保存処理は PyMuPDF で `fontfile + fontname` を指定

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 起動

```bash
python PDFTextStudio.py <your-document.pdf>
```

## テスト

依存不足で落ちないよう、`fitz` (PyMuPDF) がない環境では該当テストは自動スキップされます。

```bash
pytest -q
```

## 依存関係

- PySide6
- PyMuPDF
- Pillow
- pytest
