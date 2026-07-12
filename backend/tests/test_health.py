def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["db"] == "ok"
    assert body["data"]["redis"] == "ok"
    assert "trace_id" in body


def test_health_has_trace_id_header_roundtrip(client):
    resp = client.get("/health")
    assert resp.json()["trace_id"] != "-"
