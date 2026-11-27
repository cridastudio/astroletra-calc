# astroletra-calc

Astronomical and astrological calculation service behind [Astroletra](https://astroletra.com), a Spanish-language almanac of the sky. Python 3.12 + FastAPI, ephemerides from JPL DE440, licensed AGPL-3.0.

*[Leer en castellano](#castellano)*

## What it computes

- **Sky of the day** for any IANA time zone: Moon sign and degree at 00:00, 12:00 and 23:59, next sign change, phase, exact aspects with local time, retrogrades with their stations and the next lunation.
- **Lunations and eclipses** (new and full Moons with sign, degree and nearby eclipse), **retrograde periods** of Mercury to Saturn with shadow dates, and Besselian elements for solar eclipses (`tools/`).
- **Charts:** natal (with or without birth time), synastry with composite, solar return and yearly transits, with a clean SVG wheel.
- **Per-sign data** for a day, a week, a month or a year: houses of the Moon, aspects to the sign and its ruler, ingresses and eclipses. Data only, no interpretation.
- **Reproducible tarot draws** (Marseille deck, seeded) and HTML to PDF with WeasyPrint.

Everything is geocentric and tropical; instants are computed in UTC and returned in the requested time zone. Astrology is a cultural tradition, not a science: this service only computes where the sky objects are and the classical relations between them.

## Endpoints

All routes except `/v1/health` require the `X-Calc-Key` header (constant-time comparison with the `CALC_KEY` variable). Without `CALC_KEY` the service answers 503 to everything but `health`.

| Ruta | Cuerpo | Respuesta |
|---|---|---|
| `GET /v1/health` | – | `{ok, version, ephemeris_backend, pdf_available}` |
| `POST /v1/natal` | `{date, time\|null, lat, lon, tz, house_system:"P"}` | `{planets, houses\|null, angles\|null, aspects, balance, moon_phase, moon_range\|null, wheel_svg, has_time, warnings}` |
| `POST /v1/synastry` | `{a:{…}, b:{…}}` | `{chart_a, chart_b, inter_aspects, composite, double_wheel_svg}` |
| `POST /v1/solar-return` | `{natal:{…}, year, location:{lat,lon,tz}}` | carta del retorno + `return_datetime`, `wheel_svg`, `natal` (posiciones natales) |
| `POST /v1/transits` | `{natal:{…}, from:"YYYY-MM-DD", to:"YYYY-MM-DD"}` (máx. 400 días) | `{months:[{month, events}], retrogrades, ingresses}` |
| `POST /v1/tarot/draw` | `{spread:"three"\|"celtic", seed?, lang?:"es"\|"en"\|"ca"}` | `{seed, cards:[…], image_png_b64, image_width, image_height, placeholder_cards}` |
| `POST /v1/pdf` | `{html, base_url?}` | `application/pdf` |
| `POST /v1/lunations` | `{from, to, tz?}` (máx. 1100 días) | `{lunations:[{phase:"new"\|"full", datetime_utc, datetime_local, date_local, sign, degree, sun, moon, eclipse\|null}]}` |
| `POST /v1/retrogrades` | `{from, to, planets?, shadow?}` (máx. 1100 días) | `{periods:[{planet, from, to, days, station_retrograde, station_direct, signs, shadow_from, shadow_to}]}` |
| `POST /v1/today` | `{date, tz?}` | `{sun, moon:{sign, degree, at_00_00, at_23_59, next_sign_change, changes_sign_today, phase}, planets, aspects, retrogrades, next_lunation}` |
| `POST /v1/sign-year` | `{sign, year, tz?}` | `{sun_season, planets:[{planet, periods, ingresses}], events, eclipses, mercury_retrogrades}` |
| `POST /v1/solar-return-next` | `{natal:{…}, after?, tz?}` | `{next:{year, age, return_datetime_local, return_datetime_utc, days_until}, previous, natal_sun, warnings}` |
| `POST /v1/sign-day` | `{sign, date, tz?, lang?:"es"\|"en"}` | `{ruler, sun, moon:{…, houses_today, next_sign_change}, planets, aspects_to_sign, aspects_to_ruler, retrogrades, events, sky_aspects, featured, highlights}` |
| `POST /v1/sign-week` | `{sign, from, tz?, lang?}` (7 días desde `from`) | `{moon_by_day, moon_ingresses, aspects_to_sign, aspects_to_ruler, retrogrades, lunations, events, featured, highlights}` |
| `POST /v1/sign-month` | `{sign, year, month, tz?, lang?}` | igual que `sign-week` para el mes natural |

In `sign-day`, `sign-week` and `sign-month`, `lang` (`"es"` by default, or `"en"`) sets the language of the short data sentences (`highlights` and the `label` of each event) and of `city`; the rest of the response is the same in both languages. The sentences state facts only, and every time carries its city, as in `"La Luna entra en Escorpio, tu casa 1, a las 23:39 (hora de Madrid)."` or `"The Moon enters Scorpio, your 1st house, at 23:39 (Madrid time)."` `sign-year` has no sentences.

## Run it

With Docker:

```bash
cp .env.example .env            # set CALC_KEY
docker compose up --build       # http://localhost:8000
```

Without Docker (Python 3.12):

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
libephemeris download leb2-base  # JPL DE440 data, ~49 MB
CALC_KEY=dev-key uvicorn app.main:app --reload
pytest -q
```

## Examples

```bash
curl -s localhost:8000/v1/health

curl -s localhost:8000/v1/today -H "X-Calc-Key: dev-key" -H "content-type: application/json" \
  -d '{"date":"2026-11-24","tz":"Europe/Madrid"}'

curl -s localhost:8000/v1/natal -H "X-Calc-Key: dev-key" -H "content-type: application/json" \
  -d '{"date":"1990-04-12","time":"08:30","lat":40.4168,"lon":-3.7038,"tz":"Europe/Madrid","house_system":"P"}'

curl -s localhost:8000/v1/sign-day -H "X-Calc-Key: dev-key" -H "content-type: application/json" \
  -d '{"sign":"Scorpio","date":"2026-11-07","tz":"America/Mexico_City","lang":"en"}'
```

## How Astroletra uses it

- The free public API [`GET https://api.astroletra.com/api/v1/cielo?date=YYYY-MM-DD&tz=Europe/Madrid`](https://astroletra.com/datos/api/) serves the `/v1/today` sky of this service, precomputed every day for a list of cities (open CORS, 60 requests per minute per IP).
- The open data in [cridastudio/astroletra-datos](https://github.com/cridastudio/astroletra-datos) (lunations, eclipses, retrogrades and solar ingresses in CSV, JSON and iCal, CC BY 4.0) is exported with `tools/export_static.py`.
- Documentation of the public API: <https://astroletra.com/datos/api/>.

## License

AGPL-3.0-only (see `LICENSE`). If you run a modified version as a network service, you must offer its source to its users. Third-party components are listed in `NOTICE.md`.

Contributions are welcome: see `CONTRIBUTING.md`.

---

## Castellano

Servicio de cálculo astronómico y astrológico de [Astroletra](https://astroletra.com), el almanaque del cielo en castellano. Python 3.12 + FastAPI, efemérides JPL DE440, licencia AGPL-3.0.

**Qué calcula**
- El cielo del día en cualquier zona horaria: la Luna, las fases, los aspectos exactos con su hora local, los retrógrados y la próxima lunación.
- Las lunaciones y los eclipses, los periodos retrógrados con sus fechas de sombra y los elementos besselianos de los eclipses de Sol.
- Cartas natales, sinastría, retorno solar y tránsitos, con una rueda SVG propia.
- Los datos por signo de un día, una semana, un mes o un año. Solo datos, sin interpretación. Las frases cortas de `sign-day`, `sign-week` y `sign-month` salen en castellano y, con `"lang": "en"`, en inglés.
- Tiradas de tarot reproducibles por semilla y conversión de HTML a PDF.

**Cómo se ejecuta.** Con Docker, `docker compose up --build` después de poner `CALC_KEY` en `.env`. Las rutas y los ejemplos son los de arriba.

**Relación con la API pública.** [`/api/v1/cielo`](https://astroletra.com/datos/api/) sirve el cielo de `/v1/today` precalculado cada día, y los datos abiertos de [astroletra-datos](https://github.com/cridastudio/astroletra-datos) salen de `tools/export_static.py`.

**Licencia.** AGPL-3.0. Quien sirva una versión modificada en red tiene que ofrecer su código. Las colaboraciones son bienvenidas: lee `CONTRIBUTING.md`.
