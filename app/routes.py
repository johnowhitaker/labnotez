from __future__ import annotations

import hmac
import html
from datetime import date, datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from markdown import markdown
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .db import get_db

bp = Blueprint("main", __name__)


@bp.app_template_filter("human_date")
def human_date(value: str) -> str:
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    return parsed.strftime(f"%A, %B {parsed.day}, %Y")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalized_entry_date(raw_value: str | None) -> str:
    if not raw_value:
        return date.today().isoformat()
    parsed = datetime.strptime(raw_value, "%Y-%m-%d").date()
    return parsed.isoformat()


def _render_markdown(source: str) -> str:
    safe_source = html.escape(source or "")
    return markdown(
        safe_source,
        extensions=["extra", "sane_lists", "nl2br"],
    )


def _upload_root() -> Path:
    return Path(current_app.config["UPLOAD_DIR"])


def _allowed_image(filename: str) -> bool:
    if "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


def _save_uploaded_image(file_storage: FileStorage, entry_date: str, role: str) -> str:
    original_name = secure_filename(file_storage.filename or "")
    if not original_name:
        raise ValueError("Image filename is missing.")
    if not _allowed_image(original_name):
        raise ValueError(
            f"Unsupported image format for '{original_name}'. Use jpg, png, webp, gif, heic, or heif."
        )

    parsed_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    relative_dir = Path(f"{parsed_date.year:04d}") / f"{parsed_date.month:02d}" / f"{parsed_date.day:02d}"
    extension = Path(original_name).suffix.lower()
    filename = f"{role}-{uuid4().hex}{extension}"

    destination_dir = _upload_root() / relative_dir
    destination_dir.mkdir(parents=True, exist_ok=True)

    absolute_path = destination_dir / filename
    file_storage.save(absolute_path)

    return (relative_dir / filename).as_posix()


def _delete_image(relative_path: str) -> None:
    if not relative_path:
        return

    absolute_path = _upload_root() / relative_path
    if absolute_path.exists() and absolute_path.is_file():
        absolute_path.unlink()


def _safe_next_url(candidate: str | None) -> str | None:
    if not candidate:
        return None
    if not candidate.startswith("/") or candidate.startswith("//"):
        return None
    return candidate


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_auth"):
            flash("Please log in to access the admin area.", "warning")
            login_target = url_for("main.login", next=request.full_path.rstrip("?"))
            return redirect(login_target)
        return view(*args, **kwargs)

    return wrapped_view


def _fetch_entry_assets(entry_id: int) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    rows = get_db().execute(
        """
        SELECT id, kind, file_path, caption, sort_index
        FROM assets
        WHERE entry_id = ?
        ORDER BY
            CASE kind WHEN 'notebook_page' THEN 0 ELSE 1 END,
            sort_index ASC,
            id ASC
        """,
        (entry_id,),
    ).fetchall()

    notebook: dict[str, Any] | None = None
    photos: list[dict[str, Any]] = []
    for row in rows:
        asset = dict(row)
        asset["url"] = url_for("main.media_file", filename=asset["file_path"])
        if asset["kind"] == "notebook_page":
            notebook = asset
        else:
            photos.append(asset)

    return notebook, photos


def _fetch_entry(entry_id: int) -> dict[str, Any] | None:
    row = get_db().execute(
        """
        SELECT id, entry_date, title, body_markdown, created_at, updated_at
        FROM entries
        WHERE id = ?
        """,
        (entry_id,),
    ).fetchone()
    if row is None:
        return None

    entry = dict(row)
    notebook, photos = _fetch_entry_assets(entry_id)
    entry["notebook"] = notebook
    entry["photos"] = photos
    entry["body_html"] = _render_markdown(entry["body_markdown"])
    return entry


def _fetch_entries(page: int, per_page: int) -> tuple[list[dict[str, Any]], int]:
    total_entries = get_db().execute("SELECT COUNT(*) AS total FROM entries").fetchone()["total"]
    if total_entries == 0:
        return [], 0

    total_pages = (total_entries + per_page - 1) // per_page
    safe_page = max(1, min(page, total_pages))
    offset = (safe_page - 1) * per_page

    rows = get_db().execute(
        """
        SELECT id, entry_date, title, body_markdown, created_at, updated_at
        FROM entries
        ORDER BY entry_date DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (per_page, offset),
    ).fetchall()

    entries: list[dict[str, Any]] = []
    for row in rows:
        entry = dict(row)
        notebook, photos = _fetch_entry_assets(entry["id"])
        entry["notebook"] = notebook
        entry["photos"] = photos
        entry["body_html"] = _render_markdown(entry["body_markdown"])
        entries.append(entry)
    return entries, total_pages


def _fetch_dashboard_rows() -> list[dict[str, Any]]:
    rows = get_db().execute(
        """
        SELECT
            e.id,
            e.entry_date,
            e.title,
            e.updated_at,
            COALESCE(SUM(CASE WHEN a.kind = 'photo' THEN 1 ELSE 0 END), 0) AS photo_count,
            COALESCE(MAX(CASE WHEN a.kind = 'notebook_page' THEN 1 ELSE 0 END), 0) AS has_notebook
        FROM entries AS e
        LEFT JOIN assets AS a ON a.entry_id = e.id
        GROUP BY e.id
        ORDER BY e.entry_date DESC, e.id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _store_new_photos(
    entry_id: int,
    entry_date: str,
    files: list[FileStorage],
    captions: list[str],
    starting_sort_index: int,
    timestamp: str,
    saved_files: list[str],
) -> int:
    connection = get_db()
    sort_index = starting_sort_index
    for index, image in enumerate(files):
        if image is None or not image.filename:
            continue
        caption = captions[index].strip() if index < len(captions) else ""
        relative_path = _save_uploaded_image(image, entry_date, role="photo")
        saved_files.append(relative_path)

        connection.execute(
            """
            INSERT INTO assets (entry_id, kind, file_path, caption, sort_index, created_at)
            VALUES (?, 'photo', ?, ?, ?, ?)
            """,
            (entry_id, relative_path, caption, sort_index, timestamp),
        )
        sort_index += 1

    return sort_index


@bp.route("/")
def index():
    requested_page = request.args.get("page", default=1, type=int)
    page = requested_page if requested_page and requested_page > 0 else 1
    per_page = 20
    entries, total_pages = _fetch_entries(page=page, per_page=per_page)
    if total_pages > 0 and page > total_pages:
        page = total_pages
        entries, total_pages = _fetch_entries(page=page, per_page=per_page)

    return render_template(
        "index.html",
        entries=entries,
        page=page,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
    )


@bp.route("/entry/<int:entry_id>")
def entry_detail(entry_id: int):
    entry = _fetch_entry(entry_id)
    if entry is None:
        abort(404)
    return render_template("entry.html", entry=entry)


@bp.route("/media/<path:filename>")
def media_file(filename: str):
    return send_from_directory(_upload_root(), filename, max_age=86400)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        candidate_password = request.form.get("password", "")
        expected_password = current_app.config["ADMIN_PASSWORD"]

        if hmac.compare_digest(candidate_password, expected_password):
            session.clear()
            session["admin_auth"] = True
            session["admin_login_at"] = _utc_now_iso()

            destination = _safe_next_url(request.args.get("next"))
            return redirect(destination or url_for("main.admin_dashboard"))

        flash("Incorrect password.", "error")

    return render_template("login.html")


@bp.post("/logout")
def logout():
    session.clear()
    flash("Signed out.", "success")
    return redirect(url_for("main.index"))


@bp.route("/admin")
@admin_required
def admin_dashboard():
    entries = _fetch_dashboard_rows()
    return render_template("admin_dashboard.html", entries=entries)


@bp.route("/admin/new", methods=["GET", "POST"])
@admin_required
def admin_new():
    today_iso = date.today().isoformat()

    if request.method == "POST":
        try:
            entry_date = _normalized_entry_date(request.form.get("entry_date"))
        except ValueError:
            flash("Entry date must be in YYYY-MM-DD format.", "error")
            entry_date = today_iso

        title = request.form.get("title", "").strip()
        body_markdown = request.form.get("body_markdown", "").strip()
        notebook_caption = request.form.get("notebook_caption", "").strip()
        notebook_file = request.files.get("notebook_page")

        draft_entry = {
            "entry_date": entry_date,
            "title": title,
            "body_markdown": body_markdown,
            "notebook": {"caption": notebook_caption},
            "photos": [],
        }

        timestamp = _utc_now_iso()
        connection = get_db()
        saved_files: list[str] = []

        try:
            cursor = connection.execute(
                """
                INSERT INTO entries (entry_date, title, body_markdown, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (entry_date, title, body_markdown, timestamp, timestamp),
            )
            entry_id = cursor.lastrowid

            if notebook_file is not None and notebook_file.filename:
                notebook_path = _save_uploaded_image(notebook_file, entry_date, role="notebook")
                saved_files.append(notebook_path)
                connection.execute(
                    """
                    INSERT INTO assets (entry_id, kind, file_path, caption, sort_index, created_at)
                    VALUES (?, 'notebook_page', ?, ?, 0, ?)
                    """,
                    (entry_id, notebook_path, notebook_caption, timestamp),
                )

            _store_new_photos(
                entry_id=entry_id,
                entry_date=entry_date,
                files=request.files.getlist("photos"),
                captions=request.form.getlist("photo_caption"),
                starting_sort_index=0,
                timestamp=timestamp,
                saved_files=saved_files,
            )

            connection.commit()
        except ValueError as error:
            connection.rollback()
            for relative_path in saved_files:
                _delete_image(relative_path)
            flash(str(error), "error")
            return render_template("admin_form.html", mode="new", entry=draft_entry)
        except Exception:
            connection.rollback()
            for relative_path in saved_files:
                _delete_image(relative_path)
            flash("Could not publish entry. Please try again.", "error")
            return render_template("admin_form.html", mode="new", entry=draft_entry)

        flash("Entry published.", "success")
        return redirect(f"{url_for('main.index')}#entry-{entry_id}")

    return render_template(
        "admin_form.html",
        mode="new",
        entry={
            "entry_date": today_iso,
            "title": "",
            "body_markdown": "",
            "notebook": {"caption": ""},
            "photos": [],
        },
    )


@bp.route("/admin/edit/<int:entry_id>", methods=["GET", "POST"])
@admin_required
def admin_edit(entry_id: int):
    entry = _fetch_entry(entry_id)
    if entry is None:
        abort(404)

    if request.method == "POST":
        try:
            entry_date = _normalized_entry_date(request.form.get("entry_date"))
        except ValueError:
            flash("Entry date must be in YYYY-MM-DD format.", "error")
            return redirect(url_for("main.admin_edit", entry_id=entry_id))

        title = request.form.get("title", "").strip()
        body_markdown = request.form.get("body_markdown", "").strip()
        notebook_caption = request.form.get("notebook_caption", "").strip()
        notebook_replacement = request.files.get("notebook_page")
        delete_photo_ids = set(request.form.getlist("existing_photo_delete"))

        connection = get_db()
        timestamp = _utc_now_iso()
        saved_files: list[str] = []
        files_to_remove_after_commit: list[str] = []

        existing_notebook = connection.execute(
            """
            SELECT id, file_path
            FROM assets
            WHERE entry_id = ? AND kind = 'notebook_page'
            LIMIT 1
            """,
            (entry_id,),
        ).fetchone()

        existing_photos = connection.execute(
            """
            SELECT id, file_path
            FROM assets
            WHERE entry_id = ? AND kind = 'photo'
            ORDER BY sort_index ASC, id ASC
            """,
            (entry_id,),
        ).fetchall()
        existing_photo_paths = {str(row["id"]): row["file_path"] for row in existing_photos}

        try:
            connection.execute(
                """
                UPDATE entries
                SET entry_date = ?, title = ?, body_markdown = ?, updated_at = ?
                WHERE id = ?
                """,
                (entry_date, title, body_markdown, timestamp, entry_id),
            )

            if notebook_replacement is not None and notebook_replacement.filename:
                new_notebook_path = _save_uploaded_image(notebook_replacement, entry_date, role="notebook")
                saved_files.append(new_notebook_path)
                if existing_notebook is not None:
                    connection.execute(
                        """
                        UPDATE assets
                        SET file_path = ?, caption = ?, created_at = ?
                        WHERE id = ?
                        """,
                        (new_notebook_path, notebook_caption, timestamp, existing_notebook["id"]),
                    )
                    files_to_remove_after_commit.append(existing_notebook["file_path"])
                else:
                    connection.execute(
                        """
                        INSERT INTO assets (entry_id, kind, file_path, caption, sort_index, created_at)
                        VALUES (?, 'notebook_page', ?, ?, 0, ?)
                        """,
                        (entry_id, new_notebook_path, notebook_caption, timestamp),
                    )
            elif existing_notebook is not None:
                connection.execute(
                    "UPDATE assets SET caption = ? WHERE id = ?",
                    (notebook_caption, existing_notebook["id"]),
                )

            existing_photo_ids = request.form.getlist("existing_photo_id")
            existing_photo_captions = request.form.getlist("existing_photo_caption")
            sort_index = 0

            for index, raw_photo_id in enumerate(existing_photo_ids):
                if raw_photo_id not in existing_photo_paths:
                    continue
                photo_id = int(raw_photo_id)
                if raw_photo_id in delete_photo_ids:
                    connection.execute(
                        "DELETE FROM assets WHERE id = ? AND entry_id = ? AND kind = 'photo'",
                        (photo_id, entry_id),
                    )
                    files_to_remove_after_commit.append(existing_photo_paths[raw_photo_id])
                    continue

                caption = (
                    existing_photo_captions[index].strip()
                    if index < len(existing_photo_captions)
                    else ""
                )
                connection.execute(
                    """
                    UPDATE assets
                    SET caption = ?, sort_index = ?
                    WHERE id = ? AND entry_id = ? AND kind = 'photo'
                    """,
                    (caption, sort_index, photo_id, entry_id),
                )
                sort_index += 1

            sort_index = _store_new_photos(
                entry_id=entry_id,
                entry_date=entry_date,
                files=request.files.getlist("new_photos"),
                captions=request.form.getlist("new_photo_caption"),
                starting_sort_index=sort_index,
                timestamp=timestamp,
                saved_files=saved_files,
            )
            _ = sort_index

            connection.commit()
        except ValueError as error:
            connection.rollback()
            for relative_path in saved_files:
                _delete_image(relative_path)
            flash(str(error), "error")
            return redirect(url_for("main.admin_edit", entry_id=entry_id))
        except Exception:
            connection.rollback()
            for relative_path in saved_files:
                _delete_image(relative_path)
            flash("Could not update entry. Please try again.", "error")
            return redirect(url_for("main.admin_edit", entry_id=entry_id))

        for relative_path in files_to_remove_after_commit:
            _delete_image(relative_path)

        flash("Entry updated.", "success")
        return redirect(url_for("main.admin_edit", entry_id=entry_id))

    return render_template("admin_form.html", mode="edit", entry=entry)


@bp.post("/admin/delete/<int:entry_id>")
@admin_required
def admin_delete(entry_id: int):
    connection = get_db()
    entry = connection.execute("SELECT id FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if entry is None:
        abort(404)

    asset_rows = connection.execute(
        "SELECT file_path FROM assets WHERE entry_id = ?",
        (entry_id,),
    ).fetchall()

    connection.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    connection.commit()

    for row in asset_rows:
        _delete_image(row["file_path"])

    flash("Entry deleted.", "success")
    return redirect(url_for("main.admin_dashboard"))
