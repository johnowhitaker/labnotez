# Lab Notes Notebook

A Flask app for publishing a chronological public lab notebook with:

- optional primary handwritten notebook-page image per day
- optional gallery photos with captions
- markdown notes for each entry
- password-protected mobile-friendly admin upload flow
- SQLite + filesystem storage for restart-safe persistence

## Features

- Public timeline page with clean responsive notebook layout.
- Per-entry detail page.
- Admin login with session-based auth (`LABNOTES_ADMIN_PASSWORD`).
- Upload workflow designed for phone camera use (`accept="image/*"` + `capture`).
- Notebook page image is optional for days without handwritten notes.
- On-disk image storage organized by date: `data/uploads/YYYY/MM/DD/...`.
- SQLite schema auto-initialized on startup (`data/labnotes.db` by default).

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set at least:

- `LABNOTES_SECRET_KEY`
- `LABNOTES_ADMIN_PASSWORD`

Then run:

```bash
flask --app run.py run --host 0.0.0.0 --port 5000
```

Open:

- Public timeline: `http://localhost:5000/`
- Admin login: `http://localhost:5000/login`

## Configuration

Environment variables:

- `LABNOTES_SECRET_KEY` (required in production)
- `LABNOTES_ADMIN_PASSWORD` (required)
- `LABNOTES_DATABASE` (default: `data/labnotes.db`)
- `LABNOTES_UPLOAD_DIR` (default: `data/uploads`)
- `LABNOTES_MAX_UPLOAD_MB` (default: `64`)
- `LABNOTES_SESSION_SECURE` (`true` behind HTTPS)

## Storage Layout

```text
data/
  labnotes.db
  uploads/
    2026/
      02/
        06/
          notebook-<uuid>.jpg
          photo-<uuid>.jpg
```

This makes whole-directory backups straightforward.

## Production Notes

Use Gunicorn behind nginx/Caddy:

```bash
gunicorn --workers 2 --bind 0.0.0.0:8000 "run:app"
```

Recommended:

- set `LABNOTES_SESSION_SECURE=true` when served over HTTPS
- keep `LABNOTES_SECRET_KEY` long and random
- rotate `LABNOTES_ADMIN_PASSWORD` periodically
- add systemd restart policy for resilience

## Admin Flow

1. Log in at `/login`.
2. Go to `/admin/new`.
3. Choose date, optionally add notebook page, add gallery photos + captions, markdown notes.
4. Publish.

To edit or delete existing entries, use `/admin`.
