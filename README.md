# PDFTextStudio

**Version**: 41

日本語 PDF へのテキスト追記・移動・保存を、**PDF座標（pt）中心**で安定的に扱うための軽量 GUI ツールです。

## 主な改善点

* 座標管理の正を **PDF座標（左下原点, pt）** に統一
* `EditOperation` 抽象 + `AddTextOperation` / `MoveTextOperation` によるポリモーフィックな Undo / Redo 管理
* 保存を **PyMuPDF中心** に統一（reportlab依存を廃止）
* 日本語フォント（例: `NotoSansJP-Regular.ttf`）の選択と埋め込み
* 保存後に生成 PDF を再読み込みして表示確認
* 元PDFの上書きを禁止（別名保存のみ）

## インストール

```bash
pip install PyMuPDF Pillow
```

Tkinter が必要です（多くの環境で標準同梱）。

## 使い方

```bash
python PDFTextStudio.py <your-document.pdf>
```

### 操作手順

1. ツールバーでフォント・サイズを選択
2. 左クリックで入力位置を決定し、テキストを入力して確定
3. 右クリックで文字を選択し、ドラッグで移動
4. Undo / Redo で操作履歴を巻き戻し
5. `File > Save` で別名保存

## 座標ルール

* 内部状態: PDF座標（pt）
* 表示時のみ GUI座標（px）へ変換

```python
x_pt = (x_px - offset_x) / zoom
y_pt = page_height_pt - ((y_px - offset_y) / zoom)
```

## 非対応（現時点）

* 既存本文の直接編集
* 自動改行・再レイアウト
* 縦書き / OCR / 既存文字置換

## ファイル構成

* `PDFTextStudio.py` – 単一ファイル実装（Domain + Application + Infrastructure + UI）
* `NotoSansJP-Regular.ttf` – デフォルト候補フォント
* `README.md` – 本ドキュメント
