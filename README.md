# Flick

Pick a photo on your phone, point the phone at your laptop, swipe the photo up, and it is
saved into a folder on the laptop. Same Wi-Fi, direct connection, no cloud, no app install.

> Status: early development. Setup steps below are a placeholder until milestone M4.

## How it works

- The laptop runs one Docker container. It serves a web page to the phone and writes
  received photos into a folder you choose (for example your Desktop).
- The phone opens that page over HTTPS (self-signed certificate) and pairs by scanning a
  QR code shown on the laptop.
- A photo is sent when you swipe it up while the phone points at the laptop.

## Requirements

- Docker (Docker Desktop on macOS/Windows, Docker Engine on Linux)
- Laptop and phone on the same Wi-Fi network

## Setup

1. Copy `.env.example` to `.env` and set `HOST_IP` and `INBOX_DIR`.
2. Run `docker compose up -d`.
3. Open `http://localhost:8080/pair` on the laptop and scan the QR code with the phone.

Detailed per-OS instructions: TODO (M4).

## Configuration

See `.env.example`. Full reference: `AGENTS.md`, section 1.

## Development

```sh
pip install -r requirements.txt -r requirements-dev.txt
ruff check . && ruff format --check . && pytest
```

Contribution rules (branches, commits, milestones): see `AGENTS.md`.
