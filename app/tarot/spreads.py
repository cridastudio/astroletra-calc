"""Spread definitions with position labels in ES, EN and CA.

The position slugs are part of the public contract (clients map them to their own
labels): three = past/present/future; celtic = present, challenge, root, past,
crown, near_future, self, environment, hopes_fears, outcome.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    position: int
    slug: str
    labels: dict[str, str]

    def label_key(self, spread: str) -> str:
        """i18n key for the label (``tarot.spread.<spread>.<slug>``)."""
        return f"tarot.spread.{spread}.{self.slug}"


SPREADS: dict[str, list[Position]] = {
    "three": [
        Position(1, "past", {"es": "Pasado", "en": "Past", "ca": "Passat"}),
        Position(2, "present", {"es": "Presente", "en": "Present", "ca": "Present"}),
        Position(3, "future", {"es": "Futuro", "en": "Future", "ca": "Futur"}),
    ],
    "celtic": [
        Position(1, "present", {"es": "Situación actual", "en": "Present", "ca": "Situació actual"}),
        Position(2, "challenge", {"es": "Obstáculo", "en": "Challenge", "ca": "Obstacle"}),
        Position(3, "root", {"es": "Raíz", "en": "Root", "ca": "Arrel"}),
        Position(4, "past", {"es": "Pasado reciente", "en": "Recent past", "ca": "Passat recent"}),
        Position(5, "crown", {"es": "Lo posible", "en": "What may come", "ca": "El possible"}),
        Position(6, "near_future", {"es": "Futuro próximo", "en": "Near future", "ca": "Futur proper"}),
        Position(7, "self", {"es": "Tú", "en": "You", "ca": "Tu"}),
        Position(8, "environment", {"es": "Entorno", "en": "Environment", "ca": "Entorn"}),
        Position(9, "hopes_fears", {"es": "Esperanzas y temores", "en": "Hopes and fears", "ca": "Esperances i temors"}),
        Position(10, "outcome", {"es": "Desenlace", "en": "Outcome", "ca": "Desenllaç"}),
    ],
}
