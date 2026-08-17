import os


class Settings:
    """Config from the environment, with dev-friendly defaults."""

    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./shortener.db")
        self.base_url = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
        self.id_offset = int(os.getenv("ID_OFFSET", "100000"))
        # Reserved paths that can never be used as a custom alias.
        self.reserved = {"api", "static", "docs", "redoc", "openapi.json", "s", "health"}


settings = Settings()
