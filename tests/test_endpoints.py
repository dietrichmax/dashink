"""One test per endpoint, plus the auth paths on the protected ones.

The protected routes matter most: their failure mode is a 200 where a 401
belongs, which nothing else in the system would notice.
"""

import io

import pytest

from conftest import TOKEN, needs_font


class TestHealthz:
    def test_ok(self, client):
        # The compose healthcheck asserts status == 200 on this route, so both
        # the code and the body shape are a production contract.
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.get_json() == {"ok": True}


class TestStateJson:
    def test_returns_the_source_state(self, client):
        r = client.get("/state.json")
        assert r.status_code == 200
        assert {"node", "lang", "now", "host"} <= set(r.get_json())

    def test_is_json_serialisable(self, client):
        # `now` is a datetime in _state(); the route has to isoformat it or the
        # response 500s on encoding.
        import json

        json.dumps(client.get("/state.json").get_json())


@needs_font
class TestDashPng:
    def test_returns_a_png(self, client):
        r = client.get("/dash.png")
        assert r.status_code == 200
        assert r.mimetype == "image/png"
        assert r.data[:8] == b"\x89PNG\r\n\x1a\n"

    def test_is_the_panel_size(self, client):
        from PIL import Image

        img = Image.open(io.BytesIO(client.get("/dash.png").data))
        assert img.size == (600, 800)
        assert img.mode == "L"

    def test_is_never_cached(self, client):
        # The Kindle fetches on a timer; a cached copy freezes the panel and
        # looks exactly like a working one.
        assert "no-store" in client.get("/dash.png").headers["Cache-Control"]


class TestArtPng:
    def test_503_without_immich(self, client, app_module, monkeypatch):
        monkeypatch.setattr(app_module, "immich", None)
        assert client.get("/art.png").status_code == 503


class TestIngestMedia:
    def test_503_when_not_configured(self, client, app_module, monkeypatch):
        # No token means the endpoint is closed, rather than comparing against
        # an empty secret that anything would match.
        monkeypatch.setattr(app_module, "media", None)
        assert client.post("/ingest/media", json={}).status_code == 503

    def test_401_without_a_token(self, client, ingest):
        r = client.post("/ingest/media", json={"total": 1, "used": 1, "avail": 1})
        assert r.status_code == 401

    def test_401_with_the_wrong_token(self, client, ingest):
        r = client.post("/ingest/media", json={"total": 1, "used": 1, "avail": 1},
                        headers={"X-Dashink-Token": "wrong"})
        assert r.status_code == 401

    def test_accepts_a_valid_push(self, client, ingest):
        r = client.post("/ingest/media",
                        json={"total": 100, "used": 60, "avail": 40},
                        headers={"X-Dashink-Token": TOKEN})
        assert r.status_code == 200
        assert ingest.get()["used"] == 60

    def test_malformed_payload_is_400_not_500(self, client, ingest):
        r = client.post("/ingest/media", json={"total": "nonsense"},
                        headers={"X-Dashink-Token": TOKEN})
        assert r.status_code == 400


class TestOverride:
    def _png(self):
        from PIL import Image

        buf = io.BytesIO()
        Image.new("L", (600, 800), 255).save(buf, format="PNG")
        return buf.getvalue()

    def test_503_when_no_token_is_set(self, client, app_module, monkeypatch):
        monkeypatch.setattr(app_module, "INGEST_TOKEN", "")
        assert client.post("/override", data=b"x").status_code == 503
        assert client.delete("/override").status_code == 503

    def test_401_with_the_wrong_token(self, client, app_module, monkeypatch):
        monkeypatch.setattr(app_module, "INGEST_TOKEN", TOKEN)
        assert client.post("/override", data=b"x",
                           headers={"X-Dashink-Token": "wrong"}).status_code == 401
        assert client.delete("/override",
                             headers={"X-Dashink-Token": "wrong"}).status_code == 401

    def test_empty_body_is_400(self, client, app_module, monkeypatch):
        monkeypatch.setattr(app_module, "INGEST_TOKEN", TOKEN)
        assert client.post("/override", data=b"",
                           headers={"X-Dashink-Token": TOKEN}).status_code == 400

    def test_unreadable_image_is_400_not_500(self, client, app_module, monkeypatch):
        monkeypatch.setattr(app_module, "INGEST_TOKEN", TOKEN)
        assert client.post("/override", data=b"not an image",
                           headers={"X-Dashink-Token": TOKEN}).status_code == 400

    @needs_font
    def test_pinned_image_is_served_ahead_of_the_panel(self, client, app_module, monkeypatch):
        import sources

        pinned = self._png()
        store = sources.Expiring()
        store.put(app_module.render.render_art(pinned), 60)
        monkeypatch.setattr(app_module, "override", store)
        assert client.get("/dash.png").data == store.get()

    @needs_font
    def test_delete_clears_the_pin(self, client, app_module, monkeypatch):
        monkeypatch.setattr(app_module, "INGEST_TOKEN", TOKEN)
        r = client.post("/override", data=self._png(),
                        headers={"X-Dashink-Token": TOKEN})
        assert r.status_code == 200
        assert client.delete("/override",
                             headers={"X-Dashink-Token": TOKEN}).status_code == 200
        assert app_module.override.get() is None
