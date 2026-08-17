def create(client, url="https://example.com/page", **kw):
    return client.post("/api/links", json={"target_url": url, **kw})


def test_create_returns_short_url(client):
    res = create(client)
    assert res.status_code == 201
    body = res.json()
    assert body["short_code"]
    assert body["short_url"].endswith(body["short_code"])
    assert body["click_count"] == 0


def test_codes_are_unique(client):
    codes = {create(client, f"https://example.com/{i}").json()["short_code"] for i in range(25)}
    assert len(codes) == 25


def test_custom_alias(client):
    res = create(client, custom_alias="my-link")
    assert res.json()["short_code"] == "my-link"


def test_duplicate_alias_conflicts(client):
    create(client, custom_alias="taken")
    assert create(client, custom_alias="taken").status_code == 409


def test_reserved_alias_rejected(client):
    assert create(client, custom_alias="api").status_code == 400


def test_invalid_alias_rejected(client):
    assert create(client, custom_alias="bad alias!").status_code == 422


def test_invalid_url_rejected(client):
    assert client.post("/api/links", json={"target_url": "not-a-url"}).status_code == 422


def test_redirect_and_click_tracking(client):
    code = create(client, "https://example.com/dest").json()["short_code"]

    res = client.get(f"/{code}", headers={"referer": "https://news.ycombinator.com/item?id=1"})
    assert res.status_code == 307
    assert res.headers["location"] == "https://example.com/dest"

    client.get(f"/{code}")  # direct hit, no referrer

    stats = client.get(f"/api/links/{code}/stats").json()
    assert stats["total_clicks"] == 2
    referrers = {r["name"]: r["clicks"] for r in stats["top_referrers"]}
    assert referrers == {"news.ycombinator.com": 1, "direct": 1}


def test_clicks_by_day_is_zero_filled(client):
    code = create(client).json()["short_code"]
    client.get(f"/{code}")
    by_day = client.get(f"/api/links/{code}/stats").json()["clicks_by_day"]
    assert len(by_day) == 30
    assert by_day[-1]["clicks"] == 1
    assert by_day[0]["clicks"] == 0


def test_expired_link_returns_410(client):
    code = create(client, expires_at="2020-01-01T00:00:00Z").json()["short_code"]
    assert client.get(f"/{code}").status_code == 410


def test_unknown_code_404s(client):
    assert client.get("/nope").status_code == 404
    assert client.get("/api/links/nope/stats").status_code == 404


def test_list_includes_click_counts(client):
    code = create(client).json()["short_code"]
    client.get(f"/{code}")
    links = client.get("/api/links").json()
    assert [l["click_count"] for l in links if l["short_code"] == code] == [1]


def test_pages_render(client):
    code = create(client).json()["short_code"]
    assert client.get("/").status_code == 200
    assert client.get(f"/s/{code}").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
