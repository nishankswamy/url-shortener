"""Measure what the Redis cache actually buys on the redirect path.

    REDIS_URL=redis://localhost:6379/0 python bench.py

The interesting number is not "cache faster than database". It's the crossover:
Redis is only a win once your database round-trip costs more than a Redis
round-trip. On the same machine with SQLite that is almost never true, and the
cache makes things *slower*. Against a managed Postgres one network hop away it
is true by a wide margin.

This script measures both legs so you can see where your setup sits.
"""

import os
import statistics
import time

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/bench-shortener.db")

from app import cache, crud  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402

LINKS = 5_000
ITERATIONS = 5_000
WARMUP = 500


def percentiles(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        "p50": statistics.median(ordered) * 1e6,
        "p95": ordered[int(len(ordered) * 0.95)] * 1e6,
        "p99": ordered[int(len(ordered) * 0.99)] * 1e6,
        "mean": statistics.fmean(ordered) * 1e6,
    }


def time_it(fn, codes: list[str], iterations: int) -> list[float]:
    samples = []
    count = len(codes)
    for i in range(iterations):
        code = codes[i % count]
        start = time.perf_counter()
        fn(code)
        samples.append(time.perf_counter() - start)
    return samples


def row(label: str, stats: dict[str, float]) -> str:
    return (
        f"{label:<26} {stats['p50']:>9.1f} {stats['p95']:>9.1f} "
        f"{stats['p99']:>9.1f} {stats['mean']:>9.1f}"
    )


def main() -> None:
    print(f"Seeding {LINKS:,} links…")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        for i in range(LINKS):
            crud.create_link(db, target_url=f"https://example.com/page/{i}")
        codes = [link.short_code for link, _ in crud.list_links(db, limit=LINKS)]

    print(f"Benchmarking {ITERATIONS:,} lookups against {len(codes):,} codes\n")

    with SessionLocal() as db:
        db_lookup = lambda code: crud.get_link_by_code(db, code)  # noqa: E731
        time_it(db_lookup, codes, WARMUP)
        db_stats = percentiles(time_it(db_lookup, codes, ITERATIONS))

    cache_stats = None
    if settings.redis_url:
        cache.reset()
        with SessionLocal() as db:
            for code in codes:
                link = crud.get_link_by_code(db, code)
                cache.set_link(code, link.id, link.target_url, link.expires_at)

        # The cache degrades silently by design — if Redis is unreachable every
        # read returns None in nanoseconds. Benchmarking that path would report
        # a spectacular and completely fake speedup, so prove we have a real
        # hit before timing anything.
        if cache.get_link(codes[0]) is None:
            raise SystemExit(
                "✗ Cache returned a miss on a key that was just written.\n"
                "  Redis is unreachable, so there is nothing to benchmark.\n"
                f"  REDIS_URL={settings.redis_url}"
            )

        time_it(cache.get_link, codes, WARMUP)
        cache_stats = percentiles(time_it(cache.get_link, codes, ITERATIONS))

    print(f"{'':<26} {'p50 µs':>9} {'p95 µs':>9} {'p99 µs':>9} {'mean µs':>9}")
    print("-" * 66)
    print(row(f"database ({engine.dialect.name})", db_stats))
    if cache_stats:
        print(row("redis cache hit", cache_stats))
    print()

    if not cache_stats:
        print("No REDIS_URL set — cache leg skipped.")
        return

    delta = db_stats["p50"] - cache_stats["p50"]
    if delta > 0:
        print(f"Cache saves {delta:.0f} µs at p50 ({db_stats['p50'] / cache_stats['p50']:.1f}x).")
    else:
        print(
            f"Cache costs {-delta:.0f} µs more at p50. Your database lookup is already "
            "cheaper than a Redis round-trip — don't add the cache."
        )
    print(
        f"\nCrossover: the cache only earns its place once a database lookup costs more "
        f"than {cache_stats['p50']:.0f} µs, which is what a Redis hit costs here."
    )
    print(
        "Both numbers above are same-machine. Put either service one network hop "
        "away and add ~0.5-1 ms to it — that is the comparison that decides the "
        "architecture, not this one."
    )


if __name__ == "__main__":
    main()
