from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

from app.config import config_by_name
from app.routes.dashboard import dashboard_bp


def create_app(config_name: str = "default") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])
    app.config["UPLOAD_FOLDER"] = str(app.config["UPLOAD_FOLDER"])

    with app.app_context():
        import os

        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    app.register_blueprint(dashboard_bp)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(error):
        max_upload_mb = app.config.get("MAX_UPLOAD_MB", 200)
        message = (
            f"File is too large. Upload files up to "
            f"{max_upload_mb} MB."
        )

        if (
            request.accept_mimetypes.best == "application/json"
            or request.is_json
        ):
            return jsonify({"error": message}), 413

        return (
            render_template(
                "dashboard.html",
                dashboard=None,
                error=message,
            ),
            413,
        )

    return app
