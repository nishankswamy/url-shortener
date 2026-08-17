# Recording the demo GIF

Sixty seconds, no dead air. This is the first thing anyone sees on the repo.

## Before recording

```bash
rm -f shortener.db
python seed.py     # 5 links, ~1,400 clicks across 30 days
./run.sh
```

Seed first. An analytics page with two clicks on it reads as a broken feature.

## The shot list

1. **Home page** — five links already there with real click counts.
2. **Paste a long URL** into the form, add the alias `demo`, hit Shorten.
   Use something recognisable, like a long GitHub or docs URL.
3. **Click the new short link** — it redirects.
4. **Back, then open `stats`** on `/linux` (the seeded one with 442 clicks) so
   the chart has the spike in it.
5. **Scroll to the referrer table.**
6. End on the chart.

Don't demo the QR endpoint or the API docs. They're in the README; the GIF is
for the thing that's obvious in motion.

## Capture

macOS: `Cmd+Shift+5`, record a window, keep it under 1200px wide.
Convert with ffmpeg:

```bash
ffmpeg -i demo.mov -vf "fps=12,scale=900:-1:flags=lanczos" -loop 0 docs/demo.gif
```

Keep it under 5 MB or GitHub will refuse to inline it.
