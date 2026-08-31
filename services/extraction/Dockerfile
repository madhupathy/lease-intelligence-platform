FROM python:3.12-slim AS base

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app app \
    && mkdir -p /app/storage \
    && chown app:app /app/storage

COPY services/extraction/pyproject.toml ./
RUN pip install --no-cache-dir .

COPY services/extraction/app/ ./app/
COPY services/extraction/alembic.ini ./
COPY services/extraction/alembic/ ./alembic/
COPY services/extraction/prompts/ ./prompts/
COPY services/extraction/field_matrix.yaml ./
# Seed PDFs must be in the image for first-boot portfolio seeding on Railway.
COPY seed/ ./seed/
COPY services/extraction/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh \
    && chown -R app:app /app /docker-entrypoint.sh

USER app

ENV PORT=8080

EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint.sh"]
