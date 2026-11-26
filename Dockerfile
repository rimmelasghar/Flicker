FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --create-home --uid 1000 flick \
    && mkdir -p /data /inbox \
    && chown flick:flick /data /inbox

COPY server/ server/

USER flick

EXPOSE 8443 8080

CMD ["python", "-m", "server.main"]
