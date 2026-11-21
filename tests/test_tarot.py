import base64
import io

from PIL import Image

from app.tarot.cards import DECK, expected_asset_filenames
from app.tarot.draw import draw


def test_deck_convention():
    ids = [c.card_id for c in DECK]
    assert len(ids) == 78 and len(set(ids)) == 78
    assert ids[0] == "major_00_le_mat" and ids[21] == "major_21_le_monde"
    assert ids[8] == "major_08_la_justice" and ids[11] == "major_11_la_force"
    assert "minor_wands_01" in ids and "minor_pentacles_king" in ids
    assert expected_asset_filenames()[-1] == "minor_pentacles_king.png"


def test_seeded_draw_is_reproducible():
    a = draw("celtic", seed="astroletra-test")
    b = draw("celtic", seed="astroletra-test")
    assert [(c.card.card_id, c.reversed) for c in a.cards] == [(c.card.card_id, c.reversed) for c in b.cards]
    assert len({c.card.card_id for c in a.cards}) == 10
    c = draw("celtic", seed="another-seed")
    assert [x.card.card_id for x in a.cards] != [x.card.card_id for x in c.cards]


def test_unseeded_draw_returns_seed():
    a = draw("three")
    assert len(a.seed) == 32
    b = draw("three", seed=a.seed)
    assert [c.card.card_id for c in a.cards] == [c.card.card_id for c in b.cards]


def test_reversal_rate_is_about_one_in_five():
    reversed_count = sum(c.reversed for i in range(300) for c in draw("three", seed=f"s{i}").cards)
    assert 120 < reversed_count < 240  # 900 cards, p = 0.2 -> 180 expected


def test_draw_endpoint(client, headers):
    r = client.post("/v1/tarot/draw", json={"spread": "three", "seed": "endpoint", "lang": "en"}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["seed"] == "endpoint"
    assert [c["position"] for c in body["cards"]] == [1, 2, 3]
    assert body["cards"][0]["position_label_key"] == "past"
    assert body["reversal_probability"] == 0.2
    assert body["cards"][0]["position_label"] == "Past"
    assert body["cards"][0]["name_key"].startswith("tarot.cards.")
    img = Image.open(io.BytesIO(base64.b64decode(body["image_png_b64"])))
    assert img.format == "PNG" and img.width > 1000
    r2 = client.post("/v1/tarot/draw", json={"spread": "three", "seed": "endpoint", "lang": "en"}, headers=headers)
    assert r2.json()["cards"] == body["cards"]


def test_celtic_endpoint(client, headers):
    r = client.post("/v1/tarot/draw", json={"spread": "celtic", "lang": "ca"}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["cards"]) == 10 and body["cards"][9]["position_label"] == "Desenllaç"
    assert [c["position_label_key"] for c in body["cards"]] == ["present", "challenge", "root", "past", "crown", "near_future", "self", "environment", "hopes_fears", "outcome"]
    assert body["image_height"] > body["image_width"]


def test_forced_cards(client, headers):
    forced = [{"card_id": "minor_swords_08"}, {"card_id": "major_11_la_force", "reversed": True}, {"card_id": "minor_cups_03"}]
    r = client.post("/v1/tarot/draw", json={"spread": "three", "seed": "gold-t3-0001", "cards": forced, "lang": "es"}, headers=headers)
    assert r.status_code == 200, r.text
    cards = r.json()["cards"]
    assert [c["card_id"] for c in cards] == ["minor_swords_08", "major_11_la_force", "minor_cups_03"]
    assert cards[1]["reversed"] is True and cards[1]["name"] == "La Fuerza" and cards[1]["name_fr"] == "La Force"
    bad = client.post("/v1/tarot/draw", json={"spread": "three", "cards": forced[:2]}, headers=headers)
    assert bad.status_code == 422
    dup = client.post("/v1/tarot/draw", json={"spread": "three", "cards": [forced[0], forced[0], forced[2]]}, headers=headers)
    assert dup.status_code == 422
