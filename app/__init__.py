from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus

from app.config import config_by_name
from app.routes.dashboard import dashboard_bp
from app.routes.auth import auth_bp
from app.extensions import db, migrate, oauth

load_dotenv()


def create_app(config_name="default"):
    app = Flask(__name__)

    app.config.from_object(config_by_name[config_name])

    app.config["UPLOAD_FOLDER"] = str(app.config["UPLOAD_FOLDER"])

    # SECRET KEY
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

    # GOOGLE OAUTH
    app.config["GOOGLE_CLIENT_ID"] = os.getenv("GOOGLE_CLIENT_ID")
    app.config["GOOGLE_CLIENT_SECRET"] = os.getenv("GOOGLE_CLIENT_SECRET")

    # MYSQL (IMPORTANT FIX)
    password = quote_plus(os.getenv("MYSQL_PASSWORD"))

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{password}@"
        f"{os.getenv('MYSQL_HOST')}/{os.getenv('MYSQL_DB')}"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # INIT EXTENSIONS
    db.init_app(app)
    migrate.init_app(app, db)
    oauth.init_app(app)

    # GOOGLE REGISTER
    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    # BLUEPRINTS
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)

    # ERROR HANDLER
    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(error):
        max_upload_mb = app.config.get("MAX_UPLOAD_MB", 200)

        message = f"File is too large. Upload files up to {max_upload_mb} MB."

        if request.is_json:
            return jsonify({"error": message}), 413

        return render_template("dashboard.html", dashboard=None, error=message), 413

    return app