"""Bot detection for click counts.

Crawlers, link previewers and uptime monitors all fetch short links, and
counting them makes analytics useless — a link posted to Slack gets a click
from Slackbot before any human sees it.

This is deliberately a user-agent check and nothing more. UA strings are
trivially spoofed, so this catches honest bots (which identify themselves)
and misses dishonest ones. That's the right trade for analytics: the goal is
removing the obvious noise floor, not adversarial defence. Anything stronger
belongs in a WAF, not here.

Clicks are stored either way — `is_bot` is a label, not a filter. Throwing the
rows away would make the decision irreversible, and you can't re-derive what
you didn't keep.
"""

import re

# Substrings that appear in self-identifying automated clients.
_SIGNATURES = (
    # crawlers
    "bot", "crawler", "spider", "slurp", "archiver",
    # link previewers — the big source of phantom clicks
    "facebookexternalhit", "slackbot", "twitterbot", "linkedinbot",
    "whatsapp", "telegrambot", "discordbot", "embedly", "quora link preview",
    "skypeuripreview", "pinterest", "redditbot", "applebot",
    # tools and monitors
    "curl", "wget", "python-requests", "python-httpx", "go-http-client",
    "java/", "okhttp", "axios", "postman", "insomnia",
    "pingdom", "uptimerobot", "statuscake", "datadog", "newrelic",
    "headlesschrome", "phantomjs", "puppeteer", "playwright",
    "lighthouse", "gtmetrix",
)

_PATTERN = re.compile("|".join(re.escape(s) for s in _SIGNATURES))


def is_bot(user_agent: str | None) -> bool:
    """True if the user agent self-identifies as automated.

    A missing user agent counts as a bot. Every real browser sends one, so an
    absent header means a script that didn't bother.
    """
    if not user_agent:
        return True
    return _PATTERN.search(user_agent.lower()) is not None
