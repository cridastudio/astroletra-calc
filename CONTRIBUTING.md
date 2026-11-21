# Contributing

Thanks for helping. Issues and pull requests are welcome in English or Spanish.

## Before you start
- Open an issue first for anything larger than a small fix, so we can agree on the approach.
- Issues labelled `good first issue` are a good place to begin.

## Development
```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
libephemeris download leb2-base
pytest -q
```

## Rules
- Every change to a calculation comes with a test, and a reference value from an independent source when possible (JPL Horizons, IMCCE, the Astronomical Almanac, NASA eclipse tables). Say where the value comes from in the test.
- Keep the API contract stable: field names, the tarot deck order (seeded draws depend on it) and the `/v1/` routes. Breaking changes need a new route or version.
- No network access at runtime: the service must work offline with the downloaded ephemeris.
- By contributing you agree that your contribution is licensed under AGPL-3.0-only.

---

## Castellano
Gracias por ayudar. Las issues y los pull requests pueden ir en castellano o en inglés. Para algo más que un arreglo pequeño, abre antes una issue. Cada cambio en un cálculo lleva su prueba con un valor de referencia de una fuente independiente. No se rompe el contrato de la API, y lo que aportes queda bajo AGPL-3.0.
