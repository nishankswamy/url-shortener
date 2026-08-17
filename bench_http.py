"""End-to-end redirect latency, measured over real HTTP.

The lookup micro-benchmark in bench.py measures the wrong thing on its own —
what a user experiences is the whole request, including the click write. This
measures that, with the click write on and off the response path.

    python bench_http.py
"""

import os
import statistics
import subprocess
import sys
import time

import httpx

PORT = 8123
REQUESTS = 400
WARMUP = 40
DB = "/tmp/bench-http.db"


def percentiles(samples):
    ordered = sorted(samples)
    return {
        "p50": statistics.median(ordered) * 1000,
        "p95": ordered[int(len(ordered) * 0.95)] * 1000,
        "p99": ordered[int(len(ordered) * 0.99)] * 1000,
    }


def start_server(click_mode: str) -> subprocess.Popen:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{DB}",
        "CLICK_MODE": click_mode,
        "REDIS_URL": os.environ.get("REDIS_URL", ""),
    }
    log = open(f"/tmp/bench-http-{click_mode}.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT), "--log-level", "error"],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    for _ in range(80):
        if proc.poll() is not None:
            break
        try:
            # trust_env=False: a proxy in the environment must never sit
            # between the benchmark and localhost.
            with httpx.Client(trust_env=False, timeout=0.5) as probe:
                probe.get(f"http://127.0.0.1:{PORT}/health")
            return proc
        except Exception:  # noqa: BLE001
            time.sleep(0.25)

    proc.terminate()
    log.close()
    raise SystemExit(
        f"server did not start in {click_mode} mode — see /tmp/bench-http-{click_mode}.log:\n"
        + open(f"/tmp/bench-http-{click_mode}.log").read()[-1500:]
    )


def measure(code: str) -> dict:
    with httpx.Client(follow_redirects=False, timeout=5, trust_env=False) as client:
        url = f"http://127.0.0.1:{PORT}/{code}"
        for _ in range(WARMUP):
            client.get(url)

        samples = []
        for _ in range(REQUESTS):
            start = time.perf_counter()
            response = client.get(url)
            samples.append(time.perf_counter() - start)
            assert response.status_code == 307, response.status_code
    return percentiles(samples)


def main() -> None:
    if os.path.exists(DB):
        os.remove(DB)

    os.environ["DATABASE_URL"] = f"sqlite:///{DB}"
    from app import crud
    from app.database import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        code = crud.create_link(db, target_url="https://example.com/dest").short_code

    results = {}
    for mode in ("sync", "background"):
        proc = start_server(mode)
        try:
            results[mode] = measure(code)
        finally:
            proc.terminate()
            proc.wait()

    print(f"\n{REQUESTS} redirects, click write on and off the response path\n")
    print(f"{'':<24} {'p50 ms':>8} {'p95 ms':>8} {'p99 ms':>8}")
    print("-" * 52)
    for mode, stats in results.items():
        label = "sync (click inline)" if mode == "sync" else "background (shipped)"
        print(f"{label:<24} {stats['p50']:>8.2f} {stats['p95']:>8.2f} {stats['p99']:>8.2f}")

    saved = results["sync"]["p50"] - results["background"]["p50"]
    pct = saved / results["sync"]["p50"] * 100
    print(f"\nMoving the click write off the response path: {saved:.2f} ms at p50 ({pct:.0f}%).")


if __name__ == "__main__":
    main()
