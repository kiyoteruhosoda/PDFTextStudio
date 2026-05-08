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

## 操作

- 左クリック: 文字追加
- 右クリック: 文字選択
- 右ドラッグ: 選択文字を移動
- Deleteキー: 選択文字を削除
- ダブルクリック: 選択文字を編集
- Undo/Redo: 操作履歴を戻す/進める
- Preview Export: 一時PDFを生成して見た目確認（Previewモードへ遷移）
- Back to Edit: 元PDF表示に戻って編集再開
- Save: 別名保存（Preview中は無効。Back to Edit後に保存）

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
