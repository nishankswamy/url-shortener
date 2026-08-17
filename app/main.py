from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routes import api, pages

# Fine for a single-service demo. Day 22 capstone: use Alembic migrations.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Shortener", description="URL shortener with click analytics.")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(api.router)
app.include_router(pages.router)  # catch-all /{code} route registered last
