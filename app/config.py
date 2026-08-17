import os


class Settings:
    """Config from the environment, with dev-friendly defaults."""

    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./shortener.db")
        self.base_url = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")

        # "obfuscated" — fixed-length codes that don't reveal insertion order.
        # "sequential" — shortest possible codes, but enumerable.
        self.shortcode_mode = os.getenv("SHORTCODE_MODE", "obfuscated")

        # Only used in sequential mode, so you never hand out 1-char codes.
        self.id_offset = int(os.getenv("ID_OFFSET", "100000"))

        # "background" writes the click after the response is sent; "sync"
        # writes it inline. Kept switchable so bench.py can prove the claim in
        # the README rather than asserting it.
        self.click_mode = os.getenv("CLICK_MODE", "background")

        # Empty disables caching entirely — the app runs fine without Redis.
        self.redis_url = os.getenv("REDIS_URL", "")
        self.cache_ttl = int(os.getenv("CACHE_TTL", "3600"))

        # Comma-separated keys guarding link creation and analytics.
        # Empty means open mode — fine locally, never in production.
        self.api_keys = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]

        # Buffer clicks in Redis and flush in batches instead of one INSERT
        # per redirect. Requires REDIS_URL; falls back to direct writes.
        self.click_buffer = os.getenv("CLICK_BUFFER", "off") == "on"
        self.flush_interval = float(os.getenv("FLUSH_INTERVAL", "5"))
        self.flush_batch_size = int(os.getenv("FLUSH_BATCH_SIZE", "500"))

        # Reserved paths that can never be used as a custom alias.
        self.reserved = {"api", "static", "docs", "redoc", "openapi.json", "s", "health"}


settings = Settings()
