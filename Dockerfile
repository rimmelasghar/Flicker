FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Compose runs the container as PUID:PGID (default 1000 = flick). /data is
# sticky and world-writable so a new data volume works for any of those
# users; each file in it (key, token) is created private to its owner.
RUN useradd --create-home --uid 1000 flick \
    && mkdir -p /data /inbox \
    && chown flick:flick /data /inbox \
    && chmod 1777 /data

COPY server/ server/
COPY web/ web/

USER flick

EXPOSE 8443 8080

CMD ["python", "-m", "server.main"]
