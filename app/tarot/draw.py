"""Reproducible card draws.

Without a seed, a fresh 128-bit seed is taken from the OS CSPRNG
(``secrets``) and returned, so the same draw can be reproduced later. With a
seed, ``random.Random(seed)`` makes the draw deterministic. Reversal rule:
each card is reversed with probability 0.2 (declared on the site).
"""

from __future__ import annotations

import random
import secrets
from dataclasses import dataclass

from app.tarot.cards import CARDS_BY_ID, DECK, REVERSED_PROBABILITY, Card
from app.tarot.spreads import SPREADS, Position


@dataclass(frozen=True)
class DrawnCard:
    position: Position
    card: Card
    reversed: bool


@dataclass(frozen=True)
class Draw:
    spread: str
    seed: str
    cards: list[DrawnCard]


def draw(spread: str, seed: str | None = None, forced: list[tuple[str, bool]] | None = None) -> Draw:
    """Draw a spread. ``forced`` (list of ``(card_id, reversed)``) reproduces a known
    draw, for tests and the sample PDFs; it must have exactly one entry per position."""
    if spread not in SPREADS:
        raise ValueError(f"unknown spread: {spread}")
    positions = SPREADS[spread]
    if seed is None or seed == "":
        seed = secrets.token_hex(16)
    if forced is not None:
        if len(forced) != len(positions):
            raise ValueError(f"{spread} needs {len(positions)} cards, got {len(forced)}")
        ids = [cid for cid, _ in forced]
        if len(set(ids)) != len(ids):
            raise ValueError("forced cards must be distinct")
        cards = [DrawnCard(position=pos, card=CARDS_BY_ID[cid], reversed=rev) for pos, (cid, rev) in zip(positions, forced)]
        return Draw(spread=spread, seed=seed, cards=cards)
    rng = random.Random(seed)
    picks = rng.sample(range(len(DECK)), len(positions))
    cards = [
        DrawnCard(position=pos, card=DECK[idx], reversed=rng.random() < REVERSED_PROBABILITY)
        for pos, idx in zip(positions, picks)
    ]
    return Draw(spread=spread, seed=seed, cards=cards)


def draw_to_dict(d: Draw, lang: str = "es") -> dict:
    return {
        "seed": d.seed,
        "spread": d.spread,
        "reversal_probability": REVERSED_PROBABILITY,
        "cards": [
            {
                "position": dc.position.position,
                # Bare position slug (shared contract, see spreads.py); the i18n key is tarot.spread.<spread>.<slug>.
                "position_label_key": dc.position.slug,
                "position_label": dc.position.labels.get(lang, dc.position.labels["es"]),
                "card_id": dc.card.card_id,
                "name_key": dc.card.name_key,
                "name": dc.card.names.get(lang, dc.card.names["es"]),
                "name_fr": dc.card.name_fr,
                "arcana": dc.card.arcana,
                "number": dc.card.number,
                "suit": dc.card.suit,
                "reversed": dc.reversed,
            }
            for dc in d.cards
        ],
    }
