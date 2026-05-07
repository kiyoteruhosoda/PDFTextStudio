from __future__ import annotations

from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass(frozen=True)
class Coordinate:
    """PDF baseline coordinate (pt)."""
    x_pt: float
    y_pt: float

    @staticmethod
    def gui_to_pdf_baseline(x_px: float, y_px: float, zoom: float, page_height_pt: float, pan_offset: tuple[float, float], ascent_px: float) -> "Coordinate":
        ox, oy = pan_offset
        x_pt = (x_px - ox) / zoom
        y_top_pt = page_height_pt - ((y_px - oy) / zoom)
        return Coordinate(x_pt, y_top_pt - (ascent_px / zoom))

    def pdf_baseline_to_gui_top(self, zoom: float, page_height_pt: float, pan_offset: tuple[float, float], ascent_px: float) -> tuple[float, float]:
        ox, oy = pan_offset
        x_px = self.x_pt * zoom + ox
        baseline_y_px = (page_height_pt - self.y_pt) * zoom + oy
        return x_px, baseline_y_px - ascent_px


@dataclass
class TextElement:
    element_id: int
    page_index: int
    text: str
    coordinate: Coordinate
    font_size: float
    font_name: str
    font_path: str | None


class EditOperation(ABC):
    def __init__(self, page_index: int, element_id: int):
        self.page_index = page_index
        self.element_id = element_id

    @abstractmethod
    def execute(self, document: "Document") -> None: ...

    @abstractmethod
    def undo(self, document: "Document") -> None: ...


class AddTextOperation(EditOperation):
    def __init__(self, element: TextElement):
        super().__init__(element.page_index, element.element_id)
        self.element = element

    def execute(self, document: "Document") -> None:
        document.elements_by_page.setdefault(self.page_index, []).append(self.element)

    def undo(self, document: "Document") -> None:
        target = document.find_element(self.page_index, self.element_id)
        if target:
            document.elements_by_page[self.page_index].remove(target)


class MoveTextOperation(EditOperation):
    def __init__(self, before: TextElement, after: TextElement):
        super().__init__(after.page_index, after.element_id)
        self.before, self.after = before, after

    def execute(self, document: "Document") -> None:
        t = document.find_element(self.page_index, self.element_id)
        if t: t.coordinate = self.after.coordinate

    def undo(self, document: "Document") -> None:
        t = document.find_element(self.page_index, self.element_id)
        if t: t.coordinate = self.before.coordinate


class DeleteTextOperation(EditOperation):
    def __init__(self, element: TextElement):
        super().__init__(element.page_index, element.element_id)
        self.element = element

    def execute(self, document: "Document") -> None:
        t = document.find_element(self.page_index, self.element_id)
        if t:
            document.elements_by_page[self.page_index].remove(t)

    def undo(self, document: "Document") -> None:
        document.elements_by_page.setdefault(self.page_index, []).append(self.element)


class EditTextOperation(EditOperation):
    def __init__(self, before: TextElement, after: TextElement):
        super().__init__(after.page_index, after.element_id)
        self.before, self.after = before, after

    def execute(self, document: "Document") -> None:
        t = document.find_element(self.page_index, self.element_id)
        if t:
            t.text, t.font_size, t.font_name, t.font_path = self.after.text, self.after.font_size, self.after.font_name, self.after.font_path

    def undo(self, document: "Document") -> None:
        t = document.find_element(self.page_index, self.element_id)
        if t:
            t.text, t.font_size, t.font_name, t.font_path = self.before.text, self.before.font_size, self.before.font_name, self.before.font_path


class Document:
    def __init__(self):
        self.elements_by_page: dict[int, list[TextElement]] = {}

    def find_element(self, page_index: int, element_id: int) -> TextElement | None:
        for element in self.elements_by_page.get(page_index, []):
            if element.element_id == element_id:
                return element
        return None
