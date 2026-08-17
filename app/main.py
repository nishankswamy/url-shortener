import asyncio
import contextlib
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import clickbuffer
from .config import settings
from .routes import api, pages

logging.basicConfig(level=logging.INFO)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Run the click flusher alongside the app when buffering is on."""
    stop = asyncio.Event()
    task = None

    if settings.click_buffer:
        task = asyncio.create_task(clickbuffer.flush_loop(stop))

    yield

    if task is not None:
        stop.set()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(task, timeout=10)


app = FastAPI(
    title="Shortener",
    description="URL shortener with click analytics.",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(api.router)
app.include_router(pages.router)  # catch-all /{code} route registered last
