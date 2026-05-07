from __future__ import annotations

from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass(frozen=True)
class Coordinate:
    x_pt: float
    y_pt: float

    @staticmethod
    def gui_to_pdf(x_px: float, y_px: float, zoom: float, page_height_pt: float, pan_offset: tuple[float, float]) -> "Coordinate":
        ox, oy = pan_offset
        return Coordinate((x_px - ox) / zoom, page_height_pt - ((y_px - oy) / zoom))

    def pdf_to_gui(self, zoom: float, page_height_pt: float, pan_offset: tuple[float, float]) -> tuple[float, float]:
        ox, oy = pan_offset
        return (self.x_pt * zoom) + ox, ((page_height_pt - self.y_pt) * zoom) + oy


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
    def execute(self, document: "Document") -> None:
        ...

    @abstractmethod
    def undo(self, document: "Document") -> None:
        ...


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
        self.before = before
        self.after = after

    def execute(self, document: "Document") -> None:
        target = document.find_element(self.page_index, self.element_id)
        if target:
            target.coordinate = self.after.coordinate

    def undo(self, document: "Document") -> None:
        target = document.find_element(self.page_index, self.element_id)
        if target:
            target.coordinate = self.before.coordinate


class Document:
    def __init__(self):
        self.elements_by_page: dict[int, list[TextElement]] = {}

    def find_element(self, page_index: int, element_id: int) -> TextElement | None:
        for element in self.elements_by_page.get(page_index, []):
            if element.element_id == element_id:
                return element
        return None
