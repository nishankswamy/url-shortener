"""Populate the database with realistic demo data.

Run this before recording the demo GIF — an analytics page with two clicks on
it looks like a broken feature rather than a finished one.

    python seed.py
"""

import random
from datetime import datetime, timedelta, timezone

from app import crud, models
from app.database import Base, SessionLocal, engine

LINKS = [
    ("https://github.com/torvalds/linux", "linux", 0.30),
    ("https://docs.python.org/3/library/asyncio.html", "asyncio", 0.22),
    ("https://www.postgresql.org/docs/current/indexes.html", "pg-indexes", 0.18),
    ("https://redis.io/docs/latest/develop/use/patterns/", "redis-patterns", 0.16),
    ("https://fastapi.tiangolo.com/deployment/concepts/", None, 0.14),
]

REFERRERS = [
    ("https://news.ycombinator.com/item?id=39", 0.34),
    ("https://twitter.com/home", 0.24),
    ("https://www.reddit.com/r/programming/", 0.18),
    (None, 0.16),  # direct
    ("https://www.linkedin.com/feed/", 0.08),
]

AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121",
]

DAYS = 30
TOTAL_CLICKS = 1400


def weighted(pairs):
    values, weights = zip(*pairs)
    return random.choices(values, weights=weights, k=1)[0]


def traffic_shape(day_index: int) -> float:
    """Rising trend with a spike partway through, because real traffic is
    never flat and a flat chart makes the feature look broken."""
    base = 0.4 + 0.6 * (day_index / DAYS)
    spike = 2.6 if DAYS - 12 <= day_index <= DAYS - 9 else 1.0
    weekend = 0.6 if day_index % 7 in (5, 6) else 1.0
    return base * spike * weekend


def main() -> None:
    random.seed(7)  # same demo data every run
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        links = [
            crud.create_link(db, target_url=url, custom_alias=alias)
            for url, alias, _ in LINKS
        ]

        # Backdate creation so the list doesn't show five links made this second.
        for offset, link in enumerate(links):
            link.created_at = now - timedelta(days=DAYS - 2, hours=offset * 3)
        db.commit()

        shape = [traffic_shape(i) for i in range(DAYS)]
        total_weight = sum(shape)

        clicks = []
        for day_index, weight in enumerate(shape):
            count = round(TOTAL_CLICKS * weight / total_weight)
            day_start = now - timedelta(days=DAYS - 1 - day_index)

            for _ in range(count):
                link = weighted([(l, w) for l, (_, _, w) in zip(links, LINKS)])
                # Cluster around working hours rather than uniform across the day.
                hour = min(23, max(0, int(random.gauss(14, 4))))
                clicks.append(
                    models.Click(
                        link_id=link.id,
                        clicked_at=day_start.replace(
                            hour=hour, minute=random.randint(0, 59)
                        ),
                        referrer=crud._clean_referrer(weighted(REFERRERS)),
                        user_agent=random.choice(AGENTS),
                    )
                )

        db.add_all(clicks)
        db.commit()

        print(f"Seeded {len(links)} links and {len(clicks)} clicks over {DAYS} days.")
        for link in links:
            print(f"  /{link.short_code:<16} {crud.count_clicks(db, link.id):>5} clicks  {link.target_url}")


if __name__ == "__main__":
    main()
