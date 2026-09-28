"""Tests de htr_ottoman.normalize : un test par règle, plus NFD et idempotence."""
import unicodedata

import pytest

from htr_ottoman.config import MAKHZAN_ZIP
from htr_ottoman.normalize import normalize

MADDA, HAMZA_ABOVE, ZWNJ = "ٓ", "ٔ", "‌"


# Règle 1 : NFD (décision 5)
@pytest.mark.parametrize(
    "nfc, nfd",
    [
        ("آ", "ا" + MADDA),  # alif madda
        ("أ", "ا" + HAMZA_ABOVE),  # alif hamza
        ("ئ", "ي" + HAMZA_ABOVE),  # yāʾ hamza
    ],
)
def test_rule1_nfd_decomposes_letters(nfc, nfd):
    assert normalize(nfc) == nfd


def test_rule1_nfc_and_nfd_inputs_give_same_output():
    # Même mot encodé en NFC (Research) ou en NFD (couche gen2, Doc 83 et 6398)
    word_nfc = "سأل"
    word_nfd = unicodedata.normalize("NFD", word_nfc)
    assert word_nfc != word_nfd
    assert normalize(word_nfc) == normalize(word_nfd)


# Règle 2 : marques de direction (décision 10)
@pytest.mark.parametrize("mark", ["‎", "‏", "؜"])
def test_rule2_removes_bidi_marks(mark):
    assert normalize(f"ن{mark} ى") == "ن ى"


# Règle 3 : voyelles et signes (décision 12)
def test_rule3_removes_harakat():
    assert normalize("كُلِّ") == "كل"  # damma, kasra, shadda
    assert normalize("كتابًا") == "كتابا"  # tanwīn
    assert normalize("هٰذا") == "هذا"  # alif suscrit


def test_rule3_keeps_hamza_and_madda():
    assert normalize("آ") == "ا" + MADDA
    assert normalize("سُؤال") == "سو" + HAMZA_ABOVE + "ال"


# Règle 4 : keheh -> kaf (décision 13)
def test_rule4_keheh_to_kaf():
    assert normalize("کتاب") == "كتاب"


# Règle 5 : yāʾ persan selon la position (décision 14)
@pytest.mark.parametrize(
    "text, expected",
    [
        ("ی", "ى"),  # seul
        ("بی", "بى"),  # fin de ligne
        ("بی كتاب", "بى كتاب"),  # avant une espace
        ("بی،", "بى،"),  # avant une ponctuation
        ("بی" + ZWNJ + "دن", "بى" + ZWNJ + "دن"),  # avant un ZWNJ
        ("بیر", "بير"),  # milieu de mot
        ("یول", "يول"),  # début de mot
        ("ایلدی", "ايلدى"),  # les deux dans un mot
        ("بیِر", "بير"),  # voyelle supprimée puis milieu de mot
        ("بیٔ", "بى" + HAMZA_ABOVE),  # signe combinant ignoré pour la position
    ],
)
def test_rule5_farsi_yeh_by_position(text, expected):
    assert normalize(text) == expected


def test_rule5_keeps_arabic_yeh_and_alef_maksura():
    assert normalize("ي ى") == "ي ى"


# Règle 6 : ZWNJ répétés (décision 11)
def test_rule6_collapses_repeated_zwnj():
    assert normalize("كله" + ZWNJ * 2 + "سن") == "كله" + ZWNJ + "سن"


def test_rule6_keeps_single_zwnj():
    assert normalize("اقجه" + ZWNJ + "دن") == "اقجه" + ZWNJ + "دن"


def test_rule6_zwnj_left_repeated_after_harakat_removal():
    assert normalize("كله" + ZWNJ + "َ" + ZWNJ) == "كله" + ZWNJ


# Règle 7 : espaces (décision 9)
def test_rule7_spaces():
    assert normalize("  اول  كسك \t باش ") == "اول كسك باش"


def test_empty_and_blank():
    assert normalize("") == ""
    assert normalize("   ") == ""


# Propriétés : sortie NFD et idempotence
SAMPLES = [
    "قنده كم على نماز قلور ايدى كوزايله اولدخى قيلر ايدى",
    "عالمو جاهل شرابع موبمو کم ندر او جماق یه بنجو (؟)",
    "ڡمماٮں‎ ىرحو سلوه الحب عاشق",
    "والصّلوة على عين الانبيآء والمرسلين ؞",
    "كله‌‌ سن دخى مبارك",
    "ۀ آ أ إ ئ ؤ",
]


@pytest.mark.parametrize("text", SAMPLES)
def test_output_is_nfd(text):
    assert unicodedata.is_normalized("NFD", normalize(text))


@pytest.mark.parametrize("text", SAMPLES)
def test_idempotent(text):
    once = normalize(text)
    assert normalize(once) == once


@pytest.mark.skipif(not MAKHZAN_ZIP.exists(), reason="zip MAKHZAN absent de data/raw/")
def test_all_makhzan_ottoman_lines():
    from htr_ottoman.analysis.char_inventory import iter_lines, ottoman_pages

    n = 0
    for _, _, strings in iter_lines(ottoman_pages()):
        text = " ".join(strings)
        out = normalize(text)
        assert unicodedata.is_normalized("NFD", out)
        assert normalize(out) == out
        assert "ک" not in out and "ی" not in out
        n += 1
    assert n == 3868
