# doctool: single container (API + built web UI + LibreOffice for the office tools).
# NOT YET BUILT: Docker is not installed on the development machine, so this file is unverified;
# the Python suite was run on Linux (WSL Ubuntu) without LibreOffice. Build with:
#   docker compose build
# Before exposing it beyond localhost read docs/deployment.md (doctool has no login).

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
# LibreOffice (MPL-2.0) is an external program the office tools start; it is never linked.
# Fonts: Liberation (metric-compatible with Arial/Times/Courier) and Carlito/Caladea
# (metric-compatible with Calibri/Cambria) keep line breaks close to the Windows originals.
# tini reaps the helper processes LibreOffice starts (xpdfimport, oosplash).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libreoffice-core libreoffice-writer libreoffice-calc libreoffice-impress \
      libreoffice-draw libreoffice-pdfimport \
      fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea fonts-dejavu-core \
      tini \
 && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    DOCTOOL_DATA_DIR=/data DOCTOOL_WEB_DIR=/app/web/dist \
    DOCTOOL_HOST=0.0.0.0 DOCTOOL_ALLOW_LAN=1 DOCTOOL_PORT=8000 \
    DOCTOOL_SOFFICE=/usr/bin/soffice HOME=/data
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
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "doctool"]
