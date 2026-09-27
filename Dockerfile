FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY order_api ./order_api
COPY migrations ./migrations
COPY scripts ./scripts

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "order_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
