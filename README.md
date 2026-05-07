# PDFTextStudio

**Version**: 42

日本語 PDF へのテキスト追記・移動・保存を、**PDF座標（pt）中心**で安定的に扱う GUI ツールです。

## 主な改善点

* PDF座標を正とした `Coordinate` ドメインモデル
* `EditOperation` 抽象と `AddTextOperation` / `MoveTextOperation` のポリモーフィック Undo/Redo
* 保存を PyMuPDF に統一し、日本語フォント埋め込みを `fontfile` で指定
* フォント未設定時の警告/保存失敗を明示
* 保存後PDFを再読み込みして即時プレビュー

## インストール

```bash
pip install PyMuPDF Pillow
```

## 起動

```bash
python PDFTextStudio.py <your-document.pdf>
```

## アーキテクチャ（DDD寄り）

- `pdf_text_studio/domain/models.py`
  - `Coordinate`, `TextElement`, `EditOperation` などのドメイン
- `pdf_text_studio/app/editor.py`
  - Add/Move/Undo/Redo/Save を仲介する Application 層
- `pdf_text_studio/infrastructure/`
  - `font_manager.py`, `pdf_gateway.py` による外部依存の隔離
- `pdf_text_studio/ui/main_window.py`
  - Tkinter UI（表示・入力・ドラッグ操作）

## 座標ルール

```python
x_pt = (x_px - offset_x) / zoom
y_pt = page_height_pt - ((y_px - offset_y) / zoom)
```
