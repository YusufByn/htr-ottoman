"""Normalisation du texte : l'unique fonction, appliquée identiquement à la
vérité terrain et aux prédictions (CLAUDE.md, décisions 5 et 8).

Les règles sont appliquées dans l'ordre de RULES. Chacune est documentée
(quoi, pourquoi, exemple) et consignée dans DECISIONS.md (décisions 5, 9 à 14).

Non traités, car absents des lignes ottomanes de MAKHZAN (inventaire du
2026-09-28, reports/ottoman_characters.csv) : tatwīl, ZWJ, chiffres persans.
Les annotations des transcripteurs ({...}, (؟)) ne relèvent pas de la
normalisation : les lignes qui en contiennent sont exclues en F4 (décision 15).
"""
import re
import unicodedata

# Caractères utilisés par les règles
ZWNJ = "‌"
BIDI_MARKS = "‎‏؜"  # LRM, RLM, ALM
HARAKAT = re.compile("[ً-ْٰ]")  # tanwīn, voyelles, shadda, sukūn, alif suscrit
KEHEH, KAF = "ک", "ك"  # ک, ك
FARSI_YEH, YEH, ALEF_MAKSURA = "ی", "ي", "ى"  # ی, ي, ى


def to_nfd(text: str) -> str:
    """Règle 1 (décision 5) : forme Unicode NFD.

    Pourquoi : le modèle de départ OpenITI a été entraîné en NFD, MAKHZAN est
    surtout en NFC. Une même lettre doit avoir un seul encodage des deux côtés.
    Exemple : "آ" (U+0622) -> "ا" + madda (U+0627 U+0653).
    """
    return unicodedata.normalize("NFD", text)


def remove_bidi_marks(text: str) -> str:
    """Règle 2 (décision 10) : supprime les marques de direction LRM, RLM, ALM.

    Pourquoi : invisibles sur l'image, elles ne peuvent pas être lues par le
    modèle ; une seule occurrence dans MAKHZAN ottoman (Doc 3178).
    Exemple : "ن‎ ى" -> "ن ى".
    """
    return text.translate({ord(c): None for c in BIDI_MARKS})


def remove_harakat(text: str) -> str:
    """Règle 3 (décision 12) : supprime voyelles, tanwīn, sukūn, shadda et alif suscrit.

    Pourquoi : la convention MAKHZAN ne les transcrit pas en principe, mais ils
    sont présents de façon inégale, surtout dans le test interne. Hamza et
    madda (U+0653 à U+0655) sont gardées : elles font partie de آ, أ, ئ.
    Exemple : "كُلِّ" -> "كل".
    """
    return HARAKAT.sub("", text)


def unify_kaf(text: str) -> str:
    """Règle 4 (décision 13) : keheh ک (U+06A9) -> kaf ك (U+0643).

    Pourquoi : même lettre, deux encodages selon le clavier du transcripteur
    (persan ou arabe). L'entraînement utilise ك, le test interne surtout ک.
    Exemple : "کتاب" -> "كتاب".
    """
    return text.replace(KEHEH, KAF)


def unify_farsi_yeh(text: str) -> str:
    """Règle 5 (décision 14) : yāʾ persan ی (U+06CC) -> ى en fin de mot, ي ailleurs.

    Pourquoi : ی s'affiche sans points en fin de mot et avec points ailleurs.
    L'entraînement distingue ى (sans points) et ي (avec points) : on garde la
    même distinction visuelle. Fin de mot : le caractère suivant, signes
    combinants ignorés, n'est pas une lettre (espace, ZWNJ, ponctuation, fin).
    Exemple : "ایلدی" -> "ايلدى".
    """
    chars = list(text)
    for i, c in enumerate(chars):
        if c != FARSI_YEH:
            continue
        j = i + 1
        while j < len(chars) and unicodedata.category(chars[j]).startswith("M"):
            j += 1
        word_final = j == len(chars) or not unicodedata.category(chars[j]).startswith("L")
        chars[i] = ALEF_MAKSURA if word_final else YEH
    return "".join(chars)


def collapse_zwnj(text: str) -> str:
    """Règle 6 (décision 11) : réduit les ZWNJ répétés à un seul.

    Pourquoi : le ZWNJ a un effet visible (il empêche la liaison, comme dans
    "اقجه‌دن") et est gardé ; un ZWNJ doublé est une erreur de saisie.
    Exemple : "كله‌‌" -> "كله‌".
    """
    return re.sub(f"{ZWNJ}+", ZWNJ, text)


def normalize_spaces(text: str) -> str:
    """Règle 7 (décision 9) : réduit toute suite d'espaces à une espace, supprime
    les espaces de début et de fin.

    Pourquoi : 137 lignes ottomanes contiennent des espaces multiples ; une
    espace en trop n'est pas une erreur de lecture.
    Exemple : "  اول  كسك " -> "اول كسك".
    """
    return re.sub(r"\s+", " ", text).strip()


RULES = [
    to_nfd,
    remove_bidi_marks,
    remove_harakat,
    unify_kaf,
    unify_farsi_yeh,
    collapse_zwnj,
    normalize_spaces,
]


def normalize(text: str) -> str:
    """Applique toutes les règles dans l'ordre, puis NFD une dernière fois.

    Le résultat est toujours en NFD et la fonction est idempotente :
    normalize(normalize(x)) == normalize(x).
    """
    for rule in RULES:
        text = rule(text)
    return to_nfd(text)
