"""Tests de htr_ottoman.data.annotations (décision 15), sur des cas réels de MAKHZAN."""
import pytest

from htr_ottoman.data.annotations import has_annotation


@pytest.mark.parametrize(
    "text",
    [
        "اوفياني دكلياني يازاين دكليني {....}",  # passage illisible
        "رسول {الله} آل كتورب دعا قلدي",  # texte restitué
        "{erased lines, scribal error} اولسه قابى",  # note en anglais
        "معاش و معاد (؟) شخص واحد",  # lecture incertaine
        "معاش (؟ ) شخص",
    ],
)
def test_annotated_lines(text):
    assert has_annotation(text)


@pytest.mark.parametrize(
    "text",
    [
        "قنده كم على نماز قلور ايدى",
        "عالمو جاهل (x) ؟",  # parenthèses et point d'interrogation séparés
        "",
    ],
)
def test_plain_lines(text):
    assert not has_annotation(text)
