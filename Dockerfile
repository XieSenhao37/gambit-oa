# ---- Frontend build ----
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend

ENV HUSKY=0

RUN corepack enable && corepack prepare pnpm@9.15.9 --activate

COPY frontend/ ./
COPY backend/app/security/pages.json /backend/app/security/pages.json
RUN pnpm install --frozen-lockfile
RUN pnpm build


# ---- Backend runtime ----
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    FRONTEND_DIST_DIR=/app/static

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/run.py ./run.py
COPY backend/gunicorn.conf.py ./gunicorn.conf.py
COPY backend/scripts ./scripts
COPY backend/migrations ./migrations

# Umi build output is served by Flask from /app/static.
COPY --from=frontend-builder /frontend/dist ./static

EXPOSE 8080

CMD ["gunicorn", "-c", "gunicorn.conf.py", "-w", "4", "-b", "0.0.0.0:8080", "run:app"]
