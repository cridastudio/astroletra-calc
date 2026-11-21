def test_health(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["ephemeris_backend"] in ("libephemeris", "swisseph")
    assert body["version"]


def test_auth_required(client, reference):
    assert client.post("/v1/natal", json=reference).status_code == 401
    assert client.post("/v1/natal", json=reference, headers={"X-Calc-Key": "wrong"}).status_code == 401


def test_validation(client, headers, reference):
    bad = dict(reference, tz="Mars/Olympus")
    assert client.post("/v1/natal", json=bad, headers=headers).status_code == 422
    bad = dict(reference, time="25:00")
    assert client.post("/v1/natal", json=bad, headers=headers).status_code == 422
