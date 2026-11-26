# AGENTS.md — Flick

Instructions for the AI coding agent building Flick. Read this whole file before writing code.
Design doc (source of truth for behaviour): https://claude.ai/artifact/GPKGc8Uw76BTEkkrDznd3A

---

## 1. What we are building

Flick is a personal tool: pick a photo on the phone, point the phone at the laptop, swipe the photo up,
and it is saved quietly into a folder on the laptop. Same Wi-Fi, direct connection, no cloud.

- **Laptop:** one Docker container (FastAPI). Serves the phone web page, receives uploads, writes them
  into a mounted folder (e.g. the Desktop).
- **Phone:** a plain web page served by the container. No native app, no install.
- **HTTPS:** self-signed certificate, generated on first start, persisted in `/data`. Required because
  phone browsers only expose compass/motion sensors on secure pages.
- **Pairing:** a random token in `/data`, shown as a QR code (`https://<HOST_IP>:8443/#t=<token>`) on a
  pairing page that is reachable from the laptop only. Phone stores it in `localStorage` and sends it
  as `X-Flick-Token` on every API call.
- **Send rule:** upward swipe on the photo card **and** compass heading within ±`ANGLE_TOLERANCE`
  (default 35°) of the heading saved at calibration. No compass data → fall back to swipe-only.

### Ports and endpoints

| Method | Path | Port | Auth | Purpose |
|---|---|---|---|---|
| GET | `/` | 8443 | none | Phone web app |
| GET | `/api/ping` | 8443 | token | `{ok, host, version}` |
| POST | `/api/upload` | 8443 | token | multipart field `file`, one photo or video → `{ok, saved, bytes}` |
| GET | `/api/health` | 8443 | none | `{ok}` |
| GET | `/pair` | 8080 | laptop only | Pairing page with QR code |
| POST | `/api/token/rotate` | 8080 | laptop only | New token, unpairs all phones |

Port 8443 is published to the LAN. Port 8080 is published to `127.0.0.1` only — do **not** rely on
client-IP checks (Docker Desktop makes every request look like it comes from the gateway).

Errors: `401` bad/missing token · `413` too large · `415` not an allowed photo or video · `429` rate limited · `507` disk full.

### Config (env vars)

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `HOST_IP` | yes | — | Laptop LAN IP; used in QR code and certificate SANs |
| `INBOX_DIR` | yes | — | Host folder mounted at `/inbox` |
| `MAX_FILE_MB` | no | 50 | Per-photo cap |
| `MAX_VIDEO_MB` | no | 2048 | Per-video cap (MP4, MOV) |
| `PUID` / `PGID` | Linux | 1000 | Owner of saved files |
| `ANGLE_TOLERANCE` | no | 35 | ± degrees for the direction check |

### File saving rules

- Write to `/inbox/.flick-tmp/<random>`, then `os.replace` into `/inbox` (never a half-written file).
- Name: `YYYYMMDD-HHMMSS-<sanitised original stem>.<ext>`; add `-1`, `-2`… on collision.
- Strip path components from the uploaded name; keep only letters, digits, `-`, `_`.
- Allowed: JPEG, PNG, HEIC/HEIF, WebP, GIF photos and MP4/MOV videos — check by magic bytes (`filetype`), not extension.
- Keep original bytes (no resize, no EXIF changes).

### Target structure

```
flick/
├── AGENTS.md
├── README.md
├── docker-compose.yml
├── Dockerfile              # python:3.12-slim, non-root user
├── .env.example
├── scripts/detect-ip.sh, detect-ip.ps1
├── server/
│   ├── main.py             # starts both listeners (8443 TLS, 8080 local)
│   ├── config.py
│   ├── certs.py
│   ├── auth.py
│   ├── upload.py
│   └── pairing.py
├── web/
│   ├── index.html, styles.css, manifest.json
│   ├── app.js              # UI state, picking, upload
│   ├── gesture.js          # swipe detection
│   └── heading.js          # compass, smoothing, calibration
└── tests/
```

Python deps: `fastapi`, `uvicorn`, `python-multipart`, `cryptography`, `segno`, `filetype`;
dev: `pytest`, `httpx`, `ruff`. Frontend: vanilla HTML/CSS/JS, **no build step, no npm**.

---

## 2. Git workflow

- `main` is always runnable. Never commit directly to `main`.
- One branch per milestone, named exactly:
  `m0/repo-setup`, `m1/backend-core`, `m2/phone-page`, `m3/direction-check`, `m4/polish`, `m5/hardening`
- Branch each milestone from the latest `main`. Open a PR when the milestone's "Done when" is met;
  merge with a **merge commit** (not squash) so the individual commits stay in history.
- Do not start the next milestone until the previous PR is merged (or the human says otherwise).
- Never force-push to `main`. Force-push on your own milestone branch only to fix the last unpushed commit.

---

## 3. Commit rules

### Format — Conventional Commits

```
<type>(<scope>): <summary>

<body — optional, wrap at 72 chars>

<footer — optional>
```

**Types**

| Type | Use for |
|---|---|
| `feat` | New behaviour a user could notice |
| `fix` | Bug fix |
| `refactor` | Code change with no behaviour change |
| `test` | Adding or changing tests only |
| `docs` | README, AGENTS.md, comments-only changes |
| `build` | Dockerfile, compose, dependencies |
| `chore` | Tooling, config, `.gitignore`, scripts that are not part of the product |
| `perf` | Performance improvement |
| `style` | Formatting only (ruff format), no logic change |

**Scopes:** `server`, `auth`, `certs`, `upload`, `pairing`, `web`, `gesture`, `heading`, `docker`,
`scripts`, `tests`, `docs`. Use the narrowest one that fits; omit if the change truly spans everything.

**Summary line**

- Imperative mood: "add", "fix", "handle" — not "added", "adds", "adding".
- Lower case after the colon, no trailing full stop, **max 72 characters**.
- Says *what changed*, not *which file*: `feat(upload): save files via temp-then-rename`, not
  `update upload.py`.

**Body** (required when the *why* isn't obvious)

- Explain why, and any trade-off or follow-up. Bullet points are fine.
- Mention device testing results for anything in `gesture` / `heading`
  (e.g. "Tested on iPhone 15 Safari and Pixel 8 Chrome").

**Footer**

- `BREAKING CHANGE: <what>` if config, API or pairing format changes incompatibly.
- `Refs: M3` to tie the commit to a milestone.

### Size and content

- **One logical change per commit.** If the summary needs "and", it is probably two commits.
- Every commit must leave the project working: container builds, `pytest` passes, `ruff check` is clean.
- Tests go in the same commit as the code they test, or immediately after as `test(...)`.
- Do not mix formatting changes with logic changes.
- **Never commit:** `.env`, anything in `data/` (certificates, keys, token), uploaded images,
  `__pycache__`, `.pytest_cache`, editor folders. These must be in `.gitignore` from the first commit.
- No commented-out code, no debug `print`/`console.log` left behind.

### Examples

Good:
```
feat(certs): generate self-signed cert with host IP in SANs

Cert and key are written to /data and reused on restart so the phone
only accepts the warning once. Regenerated when HOST_IP no longer
matches the stored SAN.

Refs: M1
```
```
fix(heading): wrap angle difference across 0/360 degrees
```
```
test(upload): reject files whose bytes are not an allowed image
```

Bad:
```
update files                    # says nothing
Added upload endpoint.          # past tense, capital, full stop
feat: compass + calibration + indicator + fallback   # four commits in one
```

---

## 4. Planned commits per milestone

Treat this as the default plan. Splitting further is fine; merging items together is not. Extra
`fix(...)` commits found during testing are expected, especially in M3.

### M0 — Repo setup (`m0/repo-setup`)
1. `chore: add gitignore and editorconfig`
2. `docs: add README skeleton and AGENTS.md`
3. `build(docker): add Dockerfile, compose file and env example`

**Done when:** `docker compose up` starts a container that answers `/api/health` (plain HTTP placeholder is OK here).

### M1 — Backend core (`m1/backend-core`)
1. `feat(server): load settings from environment`
2. `feat(certs): generate self-signed cert with host IP in SANs`
3. `feat(auth): create and persist pairing token`
4. `feat(auth): require X-Flick-Token on phone API routes`
5. `feat(server): add ping and health endpoints`
6. `feat(upload): accept image upload and save to inbox`
7. `feat(pairing): serve QR pairing page on localhost-only port`
8. `feat(pairing): add token rotate endpoint`
9. `test(auth): cover missing, wrong and valid tokens`

**Done when:** `curl -k -H "X-Flick-Token: …" -F file=@x.jpg https://<HOST_IP>:8443/api/upload`
puts a file in `INBOX_DIR`; without the token returns `401`; `http://localhost:8080/pair` shows a QR code.

### M2 — Phone page (`m2/phone-page`)
1. `feat(web): add page layout and static file serving`
2. `feat(web): store pairing token from QR link fragment`
3. `feat(web): pick images from the phone gallery`
4. `feat(gesture): detect upward swipe on the photo card`
5. `feat(web): animate card off screen on flick`
6. `feat(web): upload flicked image and show status`

**Done when:** on a real phone, after scanning the QR, a photo swiped up appears in `INBOX_DIR`.

### M3 — Direction check (`m3/direction-check`)
1. `feat(heading): read compass on iOS with permission prompt`
2. `feat(heading): read compass on Android via absolute orientation`
3. `feat(heading): smooth heading with circular moving average`
4. `feat(heading): correct heading for screen orientation`
5. `feat(heading): add calibration screen and save laptop heading`
6. `feat(gesture): only send when heading is within tolerance`
7. `feat(web): show live in-range indicator`
8. `feat(heading): fall back to swipe-only when no compass data`

**Done when:** pointing at the laptop sends; turning ~90° away does not, 9 times out of 10, on both
an iPhone and an Android phone. If this cannot be met, stop and report to the human — do not lower
the bar silently.

### M4 — Polish (`m4/polish`)
1. `feat(web): stack multiple selected photos and send one per flick`
2. `feat(web): show error state with retry`
3. `feat(web): add manifest for Add to Home Screen`
4. `feat(scripts): add detect-ip scripts that write HOST_IP to .env`
5. `docs: write setup guide for macOS, Windows and Linux`

**Done when:** a fresh setup following the README takes under 5 minutes.

### M5 — Hardening (`m5/hardening`)
1. `feat(upload): validate image type by magic bytes`
2. `feat(upload): enforce per-file size limit`
3. `feat(server): add global rate limit`
4. `feat(upload): write via temp file then atomic rename`
5. `feat(upload): chown saved files to PUID/PGID on Linux`
6. `test(upload): cover size, type, naming and collisions`

**Done when:** all tests pass; wrong type → `415`, too large → `413`, wrong token → `401`.

---

## 5. Pull requests

Title: `M<n>: <milestone name>` (e.g. `M1: Backend core`). Body:

```
## What
<2–4 bullets of what this milestone adds>

## Done-when check
- [ ] <the milestone's "Done when" criterion, with how it was verified>

## Tested on
<laptop OS, phone models + browsers, or "server only">

## Notes / follow-ups
<anything deferred, known issues, questions for the human>
```

---

## 6. Code standards

- Python 3.12, type hints on all functions, `ruff check` + `ruff format` clean.
- Keep modules small and single-purpose (see structure above). No frameworks beyond those listed.
- JavaScript: ES modules, `const`/`let`, no globals except one `state` object in `app.js`.
- Log one line per received file (`received <name> (<KB> KB)`); never log the token.
- Compare tokens with `secrets.compare_digest`.

---

## 7. When to stop and ask the human

Stop and report instead of guessing when:

- A milestone's "Done when" can't be met (especially compass accuracy in M3).
- You need to change the API, ports, config variables or pairing format.
- You want to add a dependency not listed above.
- Something needs a real phone or the laptop's network and you cannot test it yourself —
  commit what you can, then list exactly what the human should test and how.

Open questions still undecided (do not decide these yourself):
- Laptop OS (affects which setup notes come first).
- Default target folder: Desktop vs a `Flick` subfolder on the Desktop.
- Silent vs a sound/notification on arrival (v1 assumption: silent).
- Keep or strip EXIF location (v1 assumption: keep).
