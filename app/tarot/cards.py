"""Deck definition and asset naming convention.

Asset files live in ``assets/tarot/<card_id>.png`` (repository root). Card ids:

- Major arcana: ``major_<NN>_<slug>`` with NN from 00 (Le Mat) to 21 (Le Monde),
  Marseille order (VIII La Justice, XI La Force).
- Minor arcana: ``minor_<suit>_<rank>`` with suits ``wands``, ``cups``, ``swords``,
  ``pentacles`` and ranks ``01``..``10``, ``page``, ``knight``, ``queen``, ``king``.

The deck order below is part of the contract: a seeded draw depends on it.
"""

from __future__ import annotations

from dataclasses import dataclass

ARCANA_MAJOR = "major"
ARCANA_MINOR = "minor"
SUITS = ["wands", "cups", "swords", "pentacles"]
RANKS = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "page", "knight", "queen", "king"]

# Declared reversal rule: each card has this probability of coming out reversed.
REVERSED_PROBABILITY = 0.2

ROMAN = ["0", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "VIIII", "X", "XI", "XII", "XIII", "XIIII", "XV", "XVI", "XVII", "XVIII", "XVIIII", "XX", "XXI"]


@dataclass(frozen=True)
class Card:
    card_id: str
    arcana: str
    number: int  # 0-21 for majors, 1-14 for minors (11 page, 12 knight, 13 queen, 14 king)
    suit: str | None
    name_fr: str  # original title on the Conver deck
    names: dict[str, str]  # es, en, ca

    @property
    def name_key(self) -> str:
        return f"tarot.cards.{self.card_id}"


_MAJORS: list[tuple[str, str, str, str, str]] = [
    # slug, FR, ES, EN, CA
    ("le_mat", "Le Mat", "El Loco", "The Fool", "El Boig"),
    ("le_bateleur", "Le Bateleur", "El Mago", "The Magician", "El Mag"),
    ("la_papesse", "La Papesse", "La Papisa", "The Popess", "La Papessa"),
    ("l_imperatrice", "L'Impératrice", "La Emperatriz", "The Empress", "L'Emperadriu"),
    ("l_empereur", "L'Empereur", "El Emperador", "The Emperor", "L'Emperador"),
    ("le_pape", "Le Pape", "El Papa", "The Pope", "El Papa"),
    ("l_amoureux", "L'Amoureux", "El Enamorado", "The Lover", "L'Enamorat"),
    ("le_chariot", "Le Chariot", "El Carro", "The Chariot", "El Carro"),
    ("la_justice", "La Justice", "La Justicia", "Justice", "La Justícia"),
    ("l_hermite", "L'Hermite", "El Ermitaño", "The Hermit", "L'Ermità"),
    ("la_roue_de_fortune", "La Roue de Fortune", "La Rueda de la Fortuna", "The Wheel of Fortune", "La Roda de la Fortuna"),
    ("la_force", "La Force", "La Fuerza", "Strength", "La Força"),
    ("le_pendu", "Le Pendu", "El Colgado", "The Hanged Man", "El Penjat"),
    ("l_arcane_sans_nom", "L'Arcane sans nom", "El Arcano sin nombre", "The Nameless Arcanum", "L'Arcà sense nom"),
    ("temperance", "Tempérance", "La Templanza", "Temperance", "La Temprança"),
    ("le_diable", "Le Diable", "El Diablo", "The Devil", "El Diable"),
    ("la_maison_dieu", "La Maison Dieu", "La Torre", "The Tower", "La Torre"),
    ("l_etoile", "L'Étoile", "La Estrella", "The Star", "L'Estrella"),
    ("la_lune", "La Lune", "La Luna", "The Moon", "La Lluna"),
    ("le_soleil", "Le Soleil", "El Sol", "The Sun", "El Sol"),
    ("le_jugement", "Le Jugement", "El Juicio", "Judgement", "El Judici"),
    ("le_monde", "Le Monde", "El Mundo", "The World", "El Món"),
]

_SUIT_NAMES = {
    "wands": {"fr": "Bâton", "es": "Bastos", "en": "Wands", "ca": "Bastos"},
    "cups": {"fr": "Coupe", "es": "Copas", "en": "Cups", "ca": "Copes"},
    "swords": {"fr": "Épée", "es": "Espadas", "en": "Swords", "ca": "Espases"},
    "pentacles": {"fr": "Denier", "es": "Oros", "en": "Pentacles", "ca": "Ors"},
}
_SUIT_PLURAL_FR = {"wands": "Bâtons", "cups": "Coupes", "swords": "Épées", "pentacles": "Deniers"}

_RANK_NAMES = {
    "01": {"fr": "As", "es": "As", "en": "Ace", "ca": "As"},
    "02": {"fr": "Deux", "es": "Dos", "en": "Two", "ca": "Dos"},
    "03": {"fr": "Trois", "es": "Tres", "en": "Three", "ca": "Tres"},
    "04": {"fr": "Quatre", "es": "Cuatro", "en": "Four", "ca": "Quatre"},
    "05": {"fr": "Cinq", "es": "Cinco", "en": "Five", "ca": "Cinc"},
    "06": {"fr": "Six", "es": "Seis", "en": "Six", "ca": "Sis"},
    "07": {"fr": "Sept", "es": "Siete", "en": "Seven", "ca": "Set"},
    "08": {"fr": "Huit", "es": "Ocho", "en": "Eight", "ca": "Vuit"},
    "09": {"fr": "Neuf", "es": "Nueve", "en": "Nine", "ca": "Nou"},
    "10": {"fr": "Dix", "es": "Diez", "en": "Ten", "ca": "Deu"},
    "page": {"fr": "Valet", "es": "Sota", "en": "Page", "ca": "Sota"},
    "knight": {"fr": "Cavalier", "es": "Caballo", "en": "Knight", "ca": "Cavall"},
    "queen": {"fr": "Reyne", "es": "Reina", "en": "Queen", "ca": "Reina"},
    "king": {"fr": "Roy", "es": "Rey", "en": "King", "ca": "Rei"},
}


def _minor_name(rank: str, suit: str, lang: str) -> str:
    r = _RANK_NAMES[rank][lang]
    if lang == "fr":
        suit_name = _SUIT_NAMES[suit]["fr"] if rank == "01" else _SUIT_PLURAL_FR[suit]
        return f"{r} de {suit_name}"
    s = _SUIT_NAMES[suit][lang]
    if lang == "en":
        return f"{r} of {s}"
    return f"{r} de {s}"


def _build_deck() -> list[Card]:
    deck: list[Card] = []
    for number, (slug, fr, es, en, ca) in enumerate(_MAJORS):
        deck.append(Card(f"major_{number:02d}_{slug}", ARCANA_MAJOR, number, None, fr, {"es": es, "en": en, "ca": ca}))
    for suit in SUITS:
        for idx, rank in enumerate(RANKS, start=1):
            deck.append(
                Card(
                    f"minor_{suit}_{rank}",
                    ARCANA_MINOR,
                    idx,
                    suit,
                    _minor_name(rank, suit, "fr"),
                    {lang: _minor_name(rank, suit, lang) for lang in ("es", "en", "ca")},
                )
            )
    return deck


DECK: list[Card] = _build_deck()
CARDS_BY_ID: dict[str, Card] = {c.card_id: c for c in DECK}
assert len(DECK) == 78, "the deck must have 78 cards"


def asset_filename(card_id: str) -> str:
    return f"{card_id}.png"


def expected_asset_filenames() -> list[str]:
    """Every PNG the asset folder is expected to contain (78 files)."""
    return [asset_filename(c.card_id) for c in DECK]
