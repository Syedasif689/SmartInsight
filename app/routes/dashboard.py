import hashlib
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
    session,
)

from werkzeug.utils import secure_filename

from app.services.dashboard_generator import generate_dashboard_from_file
from app.extensions import db
from app.models.dataset import Dataset


dashboard_bp = Blueprint("dashboard", __name__)


# =========================================================
# HOME
# =========================================================

@dashboard_bp.route("/dashboard", methods=["GET"])
def index():
    return render_template(
        "dashboard.html",
        dashboard=None,
        max_upload_mb=current_app.config["MAX_UPLOAD_MB"],
    )

# =========================================================
# HISTORY PAGE
# =========================================================

@dashboard_bp.route("/history", methods=["GET"])
def history():

    if not session.get("user"):
        return redirect(url_for("auth.login"))

    uploads = get_uploaded_files()

    return render_template(
        "history.html",
        uploads=uploads,
    )


# =========================================================
# MY UPLOADS
# =========================================================

@dashboard_bp.route("/my-uploads")
def my_uploads():

    current_user = session.get("user")

    if not current_user:
     return redirect(url_for("auth.login"))

    uploads = Dataset.query.filter_by(
        user_email=current_user["email"]
    ).order_by(Dataset.id.desc()).all()

    return render_template(
        "my_uploads.html",
        uploads=uploads
    )


# =========================================================
# FILE UPLOAD
# =========================================================

@dashboard_bp.route("/upload", methods=["POST"])
def upload_file():

    # 🔐 LOGIN CHECK
    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))

    # GET FILE
    uploaded_file = request.files.get("dataset")

    if not uploaded_file:
        return error_response(
            "Please choose a CSV or Excel file.",
            400
        )

    if uploaded_file.filename == "":
        return error_response(
            "No file selected.",
            400
        )

    if not is_allowed_file(uploaded_file.filename):
        return error_response(
            "Unsupported file type. Upload CSV, XLS or XLSX.",
            400
        )

    try:

        original_name = secure_filename(
            uploaded_file.filename
        )
        
        # Get file size for better handling
        file_size_mb = (uploaded_file.content_length or 0) / (1024 * 1024)
        max_upload_mb = current_app.config["MAX_UPLOAD_MB"]
        
        # File size validation
        if file_size_mb > max_upload_mb:
            return error_response(
                f"File size exceeds maximum ({max_upload_mb}MB). Your file is {file_size_mb:.1f}MB.",
                413
            )

        current_app.logger.info(
            f"Upload started: {original_name} (size: {file_size_mb:.2f}MB)"
        )

        # =====================================================
        # DUPLICATE DETECTION
        # =====================================================

        uploaded_hash = None
        existing_file_id = None

        if should_check_duplicates():
            uploaded_hash = hash_uploaded_file(uploaded_file)
            existing_file_id = find_existing_upload(uploaded_hash)

        if existing_file_id:

            dashboard_url = url_for(
                "dashboard.view_dashboard",
                file_id=existing_file_id
            )

            if wants_json():
                return jsonify({
                    "duplicate": True,
                    "file_id": existing_file_id,
                    "dashboard_url": dashboard_url,
                    "message": "This file was already analyzed. Showing previous results.",
                })

            return redirect(dashboard_url)

        # =====================================================
        # SAVE NEW FILE (with streaming for large files)
        # =====================================================

        unique_id = uuid4().hex

        file_id = f"{unique_id}__{original_name}"

        file_path = uploaded_file_path(file_id)

        # Use streaming save for large files
        uploaded_file.save(file_path)
        
        current_app.logger.info(
            f"File saved successfully: {file_id}"
        )

        # =====================================================
        # SAVE TO MYSQL DATABASE
        # =====================================================

        current_user = session.get("user")
        if not current_user:
            return redirect(url_for("auth.login"))

        dataset = Dataset(
            filename=original_name,
            filepath=str(file_path),
            file_id=file_id,
            user_email=current_user["email"]
        )

        db.session.add(dataset)
        db.session.commit()

        if uploaded_hash:
            write_hash_file(file_path, uploaded_hash)

        dashboard_url = url_for(
            "dashboard.view_dashboard",
            file_id=file_id
        )

        if wants_json():
            return jsonify({
                "duplicate": False,
                "file_id": file_id,
                "dashboard_url": dashboard_url,
                "file_size_mb": round(file_size_mb, 2),
            })

        return redirect(dashboard_url)

    except Exception as e:

        current_app.logger.error(f"Upload failed for {original_name}: {str(e)}", exc_info=True)

        return error_response(
            f"Failed to process dataset file: {str(e)}",
            500
        )


# =========================================================
# DASHBOARD VIEW
# =========================================================

@dashboard_bp.route("/dashboard/<file_id>", methods=["GET"])
def view_dashboard(file_id: str):

    # 🔐 LOGIN CHECK
    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))

    safe_file_id = secure_filename(file_id)

    file_path = uploaded_file_path(safe_file_id)

    if not file_path.exists():

        current_app.logger.error(
            f"File missing: {file_path}"
        )

        return render_template(
            "dashboard.html",
            dashboard=None,
            error="Uploaded file not found.",
        ), 404

    try:

        current_app.logger.info(f"Dashboard generation started for file: {safe_file_id}")
        import time
        start_time = time.time()

        # Fast-mode for smaller files to reduce processing time
        try:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
        except Exception:
            file_size_mb = None

        fast_mode = (file_size_mb is not None and file_size_mb <= 20)

        dashboard = generate_dashboard_from_file(file_path, fast=fast_mode)

        elapsed = time.time() - start_time
        current_app.logger.info(f"Dashboard generation completed in {elapsed:.2f}s for file: {safe_file_id} (fast={fast_mode})")

    except Exception as e:

        current_app.logger.error(
            f"Dashboard error for {safe_file_id}: {str(e)}",
            exc_info=True
        )

        return render_template(
            "dashboard.html",
            dashboard=None,
            error="Failed to generate dashboard.",
        ), 500

    dataset = get_dataset_for_file_id(file_id)

    return render_template(
        "dashboard.html",
        dashboard=dashboard,
        chart_data=dashboard.get("chart_data", []),
        dataset=dataset,
        file_id=file_id,
        max_upload_mb=current_app.config["MAX_UPLOAD_MB"],
    )


@dashboard_bp.route("/dashboard/<file_id>/download", methods=["GET"])
def download_dashboard(file_id: str):

    # 🔐 LOGIN CHECK
    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))

    safe_file_id = secure_filename(file_id)
    file_path = uploaded_file_path(safe_file_id)

    if not file_path.exists():
        current_app.logger.error(
            f"File missing: {file_path}"
        )
        return render_template(
            "dashboard.html",
            dashboard=None,
            error="Uploaded file not found.",
        ), 404

    try:
        dashboard = generate_dashboard_from_file(file_path)
    except Exception as e:
        current_app.logger.error(
            f"Dashboard export error: {str(e)}"
        )
        return render_template(
            "dashboard.html",
            dashboard=None,
            error="Failed to generate export file.",
        ), 500

    dataset = get_dataset_for_file_id(file_id)

    export_name = f"{display_name(file_id).rsplit('.', 1)[0]}-dashboard.html"

    if dataset:
        dataset.downloaded_filename = export_name
        dataset.downloaded_at = datetime.utcnow()
        db.session.commit()

    html_content = render_template(
        "dashboard_export.html",
        dashboard=dashboard,
    )

    response = make_response(html_content)
    response.headers["Content-Type"] = "text/html"
    response.headers[
        "Content-Disposition"
    ] = f"attachment; filename={export_name}"

    return response


# =========================================================
# HELPERS
# =========================================================

def is_allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def get_dataset_for_file_id(file_id: str):
    safe_file_id = secure_filename(file_id)
    dataset = Dataset.query.filter_by(file_id=safe_file_id).first()
    if dataset:
        return dataset

    file_path = uploaded_file_path(safe_file_id)
    dataset = Dataset.query.filter_by(filepath=str(file_path)).first()

    if not dataset:
        dataset = Dataset.query.filter(
            Dataset.filepath.like(f"%{safe_file_id}%")
        ).first()

    if dataset and not dataset.file_id:
        dataset.file_id = safe_file_id
        db.session.commit()

    return dataset


def uploaded_file_path(file_id: str) -> Path:
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    safe_file_id = secure_filename(file_id)
    return upload_folder / safe_file_id


def should_check_duplicates() -> bool:
    max_bytes = current_app.config.get("DUPLICATE_CHECK_MAX_MB", 5) * 1024 * 1024
    content_length = request.content_length
    if content_length is None:
        return True
    return content_length <= max_bytes


# =========================================================
# HASH HELPERS
# =========================================================

def hash_uploaded_file(uploaded_file) -> str:
    uploaded_file.stream.seek(0)
    file_hash = hash_stream(uploaded_file.stream)
    uploaded_file.stream.seek(0)
    return file_hash


def hash_stream(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def hash_path(file_path: Path) -> str:
    with file_path.open("rb") as file:
        return hash_stream(file)


def hash_file_path(file_path: Path) -> Path:
    return file_path.with_name(file_path.name + ".sha256")


def read_hash_file(file_path: Path):
    sidecar_path = hash_file_path(file_path)
    if sidecar_path.exists():
        return sidecar_path.read_text().strip()
    return None


def write_hash_file(file_path: Path, file_hash: str) -> None:
    try:
        hash_file_path(file_path).write_text(file_hash)
    except OSError:
        pass


# =========================================================
# DUPLICATE SEARCH
# =========================================================

def find_existing_upload(uploaded_hash: str):
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()

    allowed_extensions = {
        f".{ext}" for ext in current_app.config["ALLOWED_EXTENSIONS"]
    }

    for file_path in upload_folder.iterdir():
        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in allowed_extensions:
            continue

        existing_hash = read_hash_file(file_path)
        if not existing_hash:
            existing_hash = hash_path(file_path)
            write_hash_file(file_path, existing_hash)

        if existing_hash == uploaded_hash:
            return file_path.name

    return None


# =========================================================
# HISTORY HELPERS
# =========================================================

def get_uploaded_files():
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"]).resolve()

    allowed_extensions = {
        f".{ext}" for ext in current_app.config["ALLOWED_EXTENSIONS"]
    }

    uploads = []

    for file_path in upload_folder.iterdir():
        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in allowed_extensions:
            continue

        stat = file_path.stat()

        uploads.append({
            "file_id": file_path.name,
            "name": display_name(file_path.name),
            "size": format_file_size(stat.st_size),
            "uploaded_at": datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %Y %I:%M %p"),
            "uploaded_at_timestamp": stat.st_mtime,
            "dashboard_url": url_for("dashboard.view_dashboard", file_id=file_path.name),
        })

    uploads.sort(key=lambda x: x["uploaded_at_timestamp"], reverse=True)

    return uploads


# =========================================================
# DISPLAY HELPERS
# =========================================================

def display_name(file_name: str):
    return file_name.split("__", 1)[1] if "__" in file_name else file_name


def format_file_size(size_bytes: int):
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


# =========================================================
# REQUEST HELPERS
# =========================================================

def requested_file_id():
    payload = request.get_json(silent=True) or {}
    return payload.get("file_id") or request.form.get("file_id")


def wants_json():
    return request.is_json or request.accept_mimetypes.best == "application/json"


# =========================================================
# ERROR RESPONSE
# =========================================================

def error_response(message: str, status_code: int):
    if wants_json():
        return jsonify({"error": message}), status_code

    return render_template(
        "dashboard.html",
        dashboard=None,
        error=message,
        max_upload_mb=current_app.config["MAX_UPLOAD_MB"],
    ), status_code
