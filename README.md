# Shortener

Short links with click analytics. Day 1 of the 30-day challenge.

![demo](docs/demo.gif) <!-- record this before you call the day done -->

## Run it

```bash
./run.sh          # creates .venv, installs deps, starts on :8000
```

Then open http://localhost:8000. API docs at `/docs`.

```bash
.venv/bin/pytest  # 19 tests
```

## What it does

| Route | Purpose |
|---|---|
| `GET /` | Create links, see them listed with click counts |
| `GET /{code}` | Redirect + record the click |
| `GET /s/{code}` | Analytics page — 30-day chart, referrer table |
| `POST /api/links` | Create a link (JSON) |
| `GET /api/links` | List links with counts |
| `GET /api/links/{code}/stats` | Full stats payload |

## Architecture notes

**Codes come from the row id, not randomness.** `create_link` flushes to get the
auto-increment id, then base62-encodes `id + ID_OFFSET`. Collisions are impossible
by construction — no retry loop, no uniqueness check on the hot path. The offset
exists so you never hand out one-character codes.

The trade-off is that codes are enumerable. `app/shortcode.py` has a note on how
to keep collision-freedom while making them unguessable, which is the natural
stretch goal.

**Redirects are 307, not 301.** Browsers cache permanent redirects, so a 301
would silently stop recording clicks on repeat visits — the analytics would look
plausible and be wrong.

**Referrers are stored as host only.** Full referrer URLs are noisy to group and
leak more than the analytics need.

**Click counts come from one grouped query**, not a count per row — see
`crud.list_links`. The obvious version is an N+1.

**`clicks_by_day` zero-fills gaps** so the chart shows flat stretches instead of
connecting distant points and implying activity that didn't happen.

## Layout

```
app/
  config.py      env-driven settings
  database.py    engine + session
  models.py      Link, Click
  schemas.py     request/response validation
  shortcode.py   base62 encode/decode
  crud.py        all DB access
  routes/
    api.py       JSON API
    pages.py     HTML pages + the redirect handler
tests/           19 tests
```

## Deploy

Railway or Fly, using the Dockerfile. Set `DATABASE_URL` to your Postgres URL and
`BASE_URL` to your public domain. Nothing else changes — SQLAlchemy handles both.

## What I'd do differently

<!-- Fill this in at the end of the day. It's the section interviewers read. -->

## Stretch goals

- [ ] Redis cache on hot links — measure and record the latency delta
- [ ] Unguessable codes (see the note in `shortcode.py`)
- [ ] QR code per link
- [ ] Alembic migrations instead of `create_all`
