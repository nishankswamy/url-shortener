import pytest

from app import bots

HUMANS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 Safari",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/121.0",
]

BOTS = [
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)",
    "facebookexternalhit/1.1",
    "Twitterbot/1.0",
    "curl/8.4.0",
    "python-requests/2.31.0",
    "Mozilla/5.0 AppleWebKit/537.36 HeadlessChrome/120 Safari/537.36",
    "UptimeRobot/2.0",
]


@pytest.mark.parametrize("agent", HUMANS)
def test_browsers_are_not_bots(agent):
    assert bots.is_bot(agent) is False


@pytest.mark.parametrize("agent", BOTS)
def test_known_bots_detected(agent):
    assert bots.is_bot(agent) is True


def test_missing_user_agent_counts_as_bot():
    """Every real browser sends one. An absent header is a script."""
    assert bots.is_bot(None) is True
    assert bots.is_bot("") is True


def test_detection_is_case_insensitive():
    assert bots.is_bot("GOOGLEBOT/2.1") is True


def test_bot_clicks_excluded_from_counts(client):
    code = client.post(
        "/api/links", json={"target_url": "https://example.com/x"}
    ).json()["short_code"]

    client.get(f"/{code}", headers={"user-agent": HUMANS[0]})
    client.get(f"/{code}", headers={"user-agent": HUMANS[1]})
    client.get(f"/{code}", headers={"user-agent": "Googlebot/2.1"})
    client.get(f"/{code}", headers={"user-agent": "Slackbot-LinkExpanding 1.0"})

    stats = client.get(f"/api/links/{code}/stats").json()
    assert stats["total_clicks"] == 2
    assert stats["bot_clicks"] == 2


def test_include_bots_opts_back_in(client):
    code = client.post(
        "/api/links", json={"target_url": "https://example.com/y"}
    ).json()["short_code"]
    client.get(f"/{code}", headers={"user-agent": HUMANS[0]})
    client.get(f"/{code}", headers={"user-agent": "Googlebot/2.1"})

    stats = client.get(f"/api/links/{code}/stats?include_bots=true").json()
    assert stats["total_clicks"] == 2


def test_link_list_counts_exclude_bots(client):
    code = client.post(
        "/api/links", json={"target_url": "https://example.com/z"}
    ).json()["short_code"]
    client.get(f"/{code}", headers={"user-agent": HUMANS[0]})
    client.get(f"/{code}", headers={"user-agent": "Googlebot/2.1"})

    links = client.get("/api/links").json()
    assert [l["click_count"] for l in links if l["short_code"] == code] == [1]
