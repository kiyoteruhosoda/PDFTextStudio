# PDFTextStudio

**Version**: 43

日本語 PDF へのテキスト追記・移動・削除・編集・保存を、**PDFベースライン座標（pt）中心**で扱う GUI ツールです。

## 主な改善点

* 内部座標を **PDFベースライン座標** に統一
* `EditOperation` 抽象 + `Add/Move/Delete/Edit` のポリモーフィック Undo/Redo
* フォント未設定時は追加不可（`TTF/OTFフォントを選択してください`）
* `Preview Export` ボタンで一時PDFを生成し、保存前に見た目確認
* 保存処理は PyMuPDF で `fontfile + fontname` を指定
* source PDF は保持し、プレビュー/保存で編集正本（TextElement）を破壊しない

## インストール

```bash
pip install PyMuPDF Pillow pytest
```

## 起動

```bash
python PDFTextStudio.py <your-document.pdf>
```

## 操作

- 左クリック: 文字追加
- 右ドラッグ: 移動
- Deleteキー: 選択文字を削除
- ダブルクリック: 選択文字を編集
- Undo/Redo: 操作履歴を戻す/進める
- Preview Export: 一時PDFを生成して見た目確認（Previewモードへ遷移）
- Back to Edit: 元PDF表示に戻って編集再開
- Save: 別名保存（Preview中は無効。Back to Edit後に保存）

## 座標ルール

内部保持はベースライン座標です。

```python
# GUI top-left -> PDF baseline
x_pt = (x_px - offset_x) / zoom
y_top_pt = page_height_pt - ((y_px - offset_y) / zoom)
y_baseline_pt = y_top_pt - (ascent_px / zoom)
```
