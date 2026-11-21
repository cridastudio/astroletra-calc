import os
import sys
from pathlib import Path

os.environ.setdefault("CALC_KEY", "test-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

HEADERS = {"X-Calc-Key": "test-key"}
REFERENCE = {"date": "1990-05-14", "time": "08:30", "lat": 41.98, "lon": 2.82, "tz": "Europe/Madrid"}


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def headers() -> dict:
    return dict(HEADERS)


@pytest.fixture(scope="session")
def reference() -> dict:
    return dict(REFERENCE)
