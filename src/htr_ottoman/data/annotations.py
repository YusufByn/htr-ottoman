"""Annotations des transcripteurs dans MAKHZAN (décision 15).

Accolades : passages illisibles ({...}), texte restitué ({الله}), notes en
anglais ({erased lines, scribal error}). "(؟)" : lecture incertaine. Ce ne
sont pas des caractères du manuscrit : les lignes qui en contiennent sont
exclues de l'entraînement et de l'évaluation (F4). `normalize` ne les modifie pas.
"""
import re

ANNOTATION = re.compile(r"[{}]|\(\s*؟\s*\)")


def has_annotation(text: str) -> bool:
    return bool(ANNOTATION.search(text))
