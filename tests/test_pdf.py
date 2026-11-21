"""PDF rendering. Runs where WeasyPrint can load Pango (the Docker image); skipped otherwise."""

import pytest

from app.services import pdf as pdf_service

PARAGRAPH = (
    "<p>El Sol en Tauro a 23° habla de constancia y de apego a lo tangible; la Luna en Capricornio, "
    "en la casa siete, pide vínculos serios y duraderos. Este párrafo es texto de prueba para que el "
    "documento ocupe varias páginas y la fuente serif quede incrustada en el PDF: áéíóú ñ ç · l·l.</p>"
)


def _html(wheel_svg: str) -> str:
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Carta natal de prueba</title>
<meta name="description" content="Lectura de Astroletra, revisada por su redacción (prueba)">
<meta name="generator" content="Astroletra calc test">
<style>@page{{size:A4;margin:18mm}} body{{font-family:'DejaVu Serif',serif;font-size:11pt;line-height:1.5;color:#2a2838}}
h1,h2{{font-weight:normal}} figure{{margin:0 auto;width:150mm}} svg{{width:100%;height:auto}}</style></head>
<body><h1>Carta natal</h1><figure>{wheel_svg}</figure>
<h2>Posiciones</h2>{PARAGRAPH * 40}
<footer>Tus lecturas las elabora Astroletra con un programa propio de interpretación astrológica, y la redacción de Astroletra las revisa cada mañana.</footer>
</body></html>"""


@pytest.mark.skipif(not pdf_service.is_available(), reason="WeasyPrint needs Pango; verified in Docker")
def test_pdf_endpoint(client, headers, reference):
    natal = client.post("/v1/natal", json=reference, headers=headers).json()
    r = client.post("/v1/pdf", json={"html": _html(natal["wheel_svg"])}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")
    assert len(r.content) > 10_000


def test_pdf_unavailable_or_available(client, headers):
    r = client.post("/v1/pdf", json={"html": "<p>x</p>"}, headers=headers)
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.content.startswith(b"%PDF-")


def test_pdf_rejects_oversized_html(client, headers):
    r = client.post("/v1/pdf", json={"html": "<p>" + "x" * (8 * 1024 * 1024 + 1) + "</p>"}, headers=headers)
    assert r.status_code == 413


def test_url_fetcher_blocks_unknown_hosts():
    if not pdf_service.is_available():
        pytest.skip("WeasyPrint not importable here")
    fetcher = pdf_service.make_url_fetcher(frozenset({"astroletra.com"}))
    with pytest.raises(ValueError):
        fetcher.fetch("https://evil.example/x.png")
    with pytest.raises(ValueError):
        fetcher.fetch("file:///etc/passwd")
    assert fetcher.fetch("data:text/plain,hola") is not None


@pytest.mark.skipif(not pdf_service.is_available(), reason="WeasyPrint needs Pango; verified in Docker")
def test_pdf_external_image_is_blocked_but_render_succeeds(client, headers):
    html = '<html><body><p>hola</p><img src="https://evil.example/x.png"></body></html>'
    r = client.post("/v1/pdf", json={"html": html}, headers=headers)
    # WeasyPrint logs the failed fetch and renders the rest of the document.
    assert r.status_code == 200
