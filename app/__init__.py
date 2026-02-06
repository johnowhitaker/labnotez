from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from . import db
from .routes import bp


def _as_bool(raw_value: str | None, default: bool = False) -> bool:
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_path(raw_path: str, root_dir: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (root_dir / path).resolve()


def create_app() -> Flask:
    root_dir = Path(__file__).resolve().parent.parent
    default_database = str(root_dir / "data" / "labnotes.db")
    default_upload_dir = str(root_dir / "data" / "uploads")

    database_path = _resolve_path(os.getenv("LABNOTES_DATABASE", default_database), root_dir)
    upload_dir = _resolve_path(os.getenv("LABNOTES_UPLOAD_DIR", default_upload_dir), root_dir)

    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("LABNOTES_SECRET_KEY", "change-this-secret-key"),
        ADMIN_PASSWORD=os.getenv("LABNOTES_ADMIN_PASSWORD", "change-me"),
        DATABASE_PATH=database_path,
        UPLOAD_DIR=upload_dir,
        ALLOWED_IMAGE_EXTENSIONS={"jpg", "jpeg", "png", "webp", "gif", "heic", "heif"},
        MAX_CONTENT_LENGTH=int(os.getenv("LABNOTES_MAX_UPLOAD_MB", "64")) * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=_as_bool(os.getenv("LABNOTES_SESSION_SECURE"), default=False),
        TEMPLATES_AUTO_RELOAD=_as_bool(
            os.getenv("LABNOTES_TEMPLATE_AUTO_RELOAD"), default=False
        ),
    )

    app.config["DATABASE_PATH"].parent.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    app.register_blueprint(bp)
    return app
