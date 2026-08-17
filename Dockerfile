FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .

ENV PORT=8000
EXPOSE 8000

# Migrate before serving. If the migration fails the container fails, which is
# what you want — a container serving against the wrong schema is worse than
# one that won't start.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
