"""HTML to PDF with WeasyPrint.

WeasyPrint is imported lazily so the rest of the service works on machines
without Pango (the Docker image always has it). Remote fetches are limited to
``data:`` URIs and to http(s) hosts listed in ``PDF_ALLOWED_HOSTS``; everything
else (``file://`` included) is refused and WeasyPrint renders without it.
"""

from __future__ import annotations

from functools import cache
from typing import Any
from urllib.parse import urlsplit


class PdfUnavailable(RuntimeError):
    pass


@cache
def _import_weasyprint() -> tuple[Any, str | None]:
    try:
        import weasyprint  # noqa: WPS433 (lazy import on purpose)
    except (ImportError, OSError) as exc:  # OSError: missing pango/cairo libraries
        return None, str(exc)
    return weasyprint, None


def _load_weasyprint() -> Any:
    module, error = _import_weasyprint()
    if module is None:
        raise PdfUnavailable(f"WeasyPrint is not available: {error}")
    return module


def is_available() -> bool:
    try:
        _load_weasyprint()
    except PdfUnavailable:
        return False
    return True


def make_url_fetcher(allowed_hosts: frozenset[str]) -> Any:
    """Return a ``weasyprint.urls.URLFetcher`` restricted to data: URIs and allowed hosts."""
    weasyprint = _load_weasyprint()
    from weasyprint.urls import URLFetcher  # noqa: WPS433

    class RestrictedFetcher(URLFetcher):  # type: ignore[misc]
        def fetch(self, url: str, headers: Any = None) -> Any:
            parts = urlsplit(url)
            scheme = parts.scheme.lower()
            if scheme == "data":
                return super().fetch(url, headers)
            if scheme in ("http", "https") and (parts.hostname or "").lower() in allowed_hosts:
                return super().fetch(url, headers)
            raise ValueError(f"URL not allowed by PDF_ALLOWED_HOSTS: {url}")

    del weasyprint
    return RestrictedFetcher(timeout=10, allowed_protocols={"data", "http", "https"}, fail_on_errors=False)


def render_pdf(html: str, *, base_url: str | None, allowed_hosts: frozenset[str]) -> bytes:
    weasyprint = _load_weasyprint()
    fetcher = make_url_fetcher(allowed_hosts)
    document = weasyprint.HTML(string=html, base_url=base_url, url_fetcher=fetcher)
    return document.write_pdf()
