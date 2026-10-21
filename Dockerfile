# doctool: single container (API + built web UI). NOT YET RUN: Docker is not installed on the
# development machine, so this file is unverified. Build with: docker compose build

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    DOCTOOL_DATA_DIR=/data DOCTOOL_WEB_DIR=/app/web/dist \
    DOCTOOL_HOST=0.0.0.0 DOCTOOL_ALLOW_LAN=1 DOCTOOL_PORT=8000
WORKDIR /app/api
COPY api/pyproject.toml ./
COPY api/doctool ./doctool
RUN pip install --no-cache-dir .
COPY --from=web /web/dist /app/web/dist
RUN useradd --create-home --uid 10001 doctool && mkdir /data && chown doctool /data
USER doctool
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/v1/health')"
CMD ["python", "-m", "doctool"]
