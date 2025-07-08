# PDFTextStudio

**Version**: 33

A lightweight Python GUI application for annotating PDF files with custom text. Easily add, move, and style text anywhere on the page, then export your changes as a new PDF.

## Features

* **Add Text**: Click anywhere on the PDF to insert new text.
* **Drag & Drop**: Right‑click a text element to select and drag it to a new position.
* **Zoom**: Use the mouse wheel to zoom in and out, with text positions and hit‑tests automatically adjusted.
* **Undo/Redo**: Revert or re‑apply your last text additions and moves.
* **Font Support**: Choose from system `.ttf` fonts or add new ones at runtime.
* **Multi‑Page**: Navigate through pages with `Prev`/`Next` buttons.
* **Save PDF**: Export your annotated document to a new PDF file.

## Installation

1. Clone or download this repository.
2. Install required Python packages:

   ```bash
   pip install PyMuPDF Pillow reportlab
   ```
3. Ensure you have Tkinter available (usually included with most Python installs).

## Usage

```bash
python pdf_editor.py <your-document.pdf>
```

* The application window titled **PDFTextStudio v33** will open.
* Use the **Font** and **Size** selectors on the toolbar to configure text style.
* **Left‑click** to add text. Enter your content in the prompt.
* **Right‑click** a text element to select it (highlighted in blue), then drag.
* Use the **Prev** and **Next** buttons to switch pages.
* Click **Save** in the File menu to export your edits.

## File Structure

* `pdf_editor.py` – Main application script (PDFModel, PDFView, PDFController).
* `README.md` – This documentation.

## License

MIT License © 2025
