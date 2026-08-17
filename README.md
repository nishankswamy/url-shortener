# Shortener

Short links with click analytics. Day 1 of a 30-day build challenge.

![demo](docs/demo.gif) <!-- record this before calling the day done -->

## Run it

```bash
./run.sh                    # creates .venv, installs deps, starts on :8000
python seed.py              # optional: 5 links and ~1,400 backdated clicks
.venv/bin/pytest            # 34 tests
```

Open http://localhost:8000. API docs at `/docs`.

## What it does

| Route | Purpose |
|---|---|
| `GET /` | Create links, see them listed with click counts |
| `GET /{code}` | Redirect + record the click |
| `GET /s/{code}` | Analytics — 30-day chart, referrer table |
| `POST /api/links` | Create a link |
| `GET /api/links` | List with click counts |
| `GET /api/links/{code}/stats` | Full stats payload |
| `GET /api/links/{code}/qr.png` | QR code for the short URL |

## Design decisions

### Codes come from the row id, not randomness

`create_link` flushes to get the auto-increment id, then derives the code from
it. Collisions are impossible by construction — no retry loop, no uniqueness
check on the hot path.

The naive version of this (`encode(id)`) is enumerable: given one code you can
walk the entire table. The fix isn't randomness, which reintroduces collisions,
but a **bijection over the code space** — multiply the id by a constant coprime
with the modulus:

```
id 1000 -> OFLAh2
id 1001 -> QoHeiF
id 1002 -> S7CSki
```

Still one-to-one, so still collision-free, but no longer ordered. `SHORTCODE_MODE`
switches between `obfuscated` (default, fixed 6 chars) and `sequential` (shortest
possible, enumerable).

This is obfuscation, not encryption — the multiplier is in the source. It stops
casual enumeration; it does not make a link secret. Anything genuinely private
needs authorisation on the redirect.

### Redirects are 307, not 301

Browsers cache permanent redirects. A 301 would silently stop recording clicks on
repeat visits, and the analytics would look plausible while being wrong.

### The cache is opt-in, because measuring said it wasn't worth it

See the benchmark below. `REDIS_URL` is empty by default and the app runs fine
without Redis — every cache failure path falls through to the database.

### Click counts come from one grouped query

`crud.list_links` joins and groups. The obvious implementation is an N+1.

### `clicks_by_day` zero-fills gaps

Otherwise the chart connects distant points and implies activity that didn't
happen.

## Benchmarks

Two optimisations, both measured before being believed.

**Lookup path** — `python bench.py`, 5,000 links, 5,000 lookups:

| | p50 | p95 | p99 |
|---|---|---|---|
| SQLite (indexed) | 87.0 µs | 96.5 µs | 126.2 µs |
| Redis hit | 82.2 µs | 93.3 µs | 106.6 µs |

**1.1x.** An indexed lookup against a local SQLite file costs about the same as a
Redis round-trip, so the cache buys nothing here. It only earns its place once a
database lookup costs more than ~82 µs — which is roughly what one network hop to
a managed Postgres adds.

**End-to-end redirect** — `python bench_http.py`, 400 requests, click write on and
off the response path:

| run | sync p50 | background p50 |
|---|---|---|
| 1 | 2.27 ms | 2.50 ms |
| 2 | 2.69 ms | 2.43 ms |
| 3 | 2.27 ms | 2.49 ms |

The direction **flips between runs** — the difference is inside run-to-run
variance. Moving the click write off the response path is not a measurable win at
this scale, with one serial client and a local SQLite file.

Both optimisations are kept, both are off or neutral by default, and both are bets
on a deployment that doesn't exist yet: a remote Postgres and concurrent traffic.
That's a defensible reason to keep code. "It felt faster" is not.

The measurement discipline mattered more than the result. The first version of
`bench.py` reported a **678x speedup** — it was timing the cache's own
graceful-degradation path, which returns `None` in nanoseconds when Redis is
unreachable. `bench.py` now asserts a real cache hit before timing anything.

## Layout

```
app/
  config.py      env-driven settings
  database.py    engine + session
  models.py      Link, Click
  schemas.py     request/response validation
  shortcode.py   base62 + the id->code bijection
  cache.py       Redis with graceful degradation
  crud.py        all DB access
  routes/
    api.py       JSON API
    pages.py     HTML pages + the redirect handler
bench.py         lookup micro-benchmark
bench_http.py    end-to-end redirect benchmark
seed.py          demo data
tests/           34 tests
```

## Config

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./shortener.db` | Postgres works unchanged |
| `BASE_URL` | `http://localhost:8000` | Used to build short URLs |
| `SHORTCODE_MODE` | `obfuscated` | or `sequential` |
| `REDIS_URL` | *(empty)* | Empty disables the cache |
| `CACHE_TTL` | `3600` | Seconds |
| `CLICK_MODE` | `background` | or `sync`; exists so the benchmark is reproducible |

## Deploy

Railway or Fly, using the Dockerfile. Set `DATABASE_URL` and `BASE_URL`. Nothing
else changes.

## What I'd do differently

<!-- Fill this in at the end of the day. It's the section interviewers read. -->

## Known gaps

- `Base.metadata.create_all` instead of Alembic migrations
- No auth — anyone can create links and read anyone's analytics
- Click writes go straight to Postgres; at real volume they should be buffered
  in Redis and flushed in batches
- No bot filtering, so the click counts include crawlers
