"""Lecture d'un fichier ALTO (v4, export eScriptorium).

Structure : Page -> TextBlock -> TextLine -> String. Chaque TextLine porte une
ligne de base (BASELINE) et un polygone (Shape/Polygon), en pixels de l'image.
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

Point = tuple[int, int]


@dataclass
class Line:
    line_id: str
    block_id: str
    text: str  # CONTENT des String, joints par une espace, non normalisé
    baseline: list[Point] = field(default_factory=list)
    polygon: list[Point] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass
class Page:
    image_filename: str
    width: int
    height: int
    lines: list[Line]


def _points(value: str | None) -> list[Point]:
    """"x1 y1 x2 y2 ..." -> [(x1, y1), (x2, y2), ...]"""
    if not value:
        return []
    nums = [int(float(v)) for v in value.replace(",", " ").split()]
    return list(zip(nums[0::2], nums[1::2]))


def read_alto(source: bytes | str) -> Page:
    """Lit un ALTO depuis son contenu (bytes ou texte XML)."""
    root = ET.fromstring(source)
    ns = {"a": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {"a": ""}
    q = (lambda tag: f"a:{tag}") if ns["a"] else (lambda tag: tag)

    page = root.find(f".//{q('Page')}", ns)
    image = root.findtext(f".//{q('sourceImageInformation')}/{q('fileName')}", default="", namespaces=ns)
    lines = []
    for block in root.iterfind(f".//{q('TextBlock')}", ns):
        for tl in block.iterfind(q("TextLine"), ns):
            strings = [s.get("CONTENT", "") for s in tl.iterfind(q("String"), ns)]
            polygon = tl.find(f"{q('Shape')}/{q('Polygon')}", ns)
            lines.append(
                Line(
                    line_id=tl.get("ID", ""),
                    block_id=block.get("ID", ""),
                    text=" ".join(strings),
                    baseline=_points(tl.get("BASELINE")),
                    polygon=_points(polygon.get("POINTS") if polygon is not None else None),
                )
            )
    return Page(
        image_filename=image.strip(),
        width=int(float(page.get("WIDTH", 0))),
        height=int(float(page.get("HEIGHT", 0))),
        lines=lines,
    )
