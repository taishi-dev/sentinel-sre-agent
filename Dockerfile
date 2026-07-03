FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    APP_TARGET=shop.app:create_app

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY scenarios ./scenarios
RUN pip install .

EXPOSE 8080
# APP_TARGET selects the service: shop.app:create_app (default) or
# sentinel.server:create_app once the sentinel entrypoint is wired (Plan 4 Task 10).
CMD ["sh", "-c", "exec uvicorn ${APP_TARGET} --factory --host 0.0.0.0 --port ${PORT}"]
