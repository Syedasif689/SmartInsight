from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv
import os
import logging
import sys
from urllib.parse import quote_plus
from email.utils import parseaddr

from app.config import config_by_name
from app.extensions import db, migrate, oauth, mail
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()


def configure_logging(app):
    app.logger.setLevel(logging.INFO)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    ))

    if not any(
        isinstance(handler, logging.StreamHandler)
        and getattr(handler, "stream", None) is sys.stdout
        for handler in app.logger.handlers
    ):
        app.logger.addHandler(stdout_handler)


def database_uri_from_env():
    mysql_url = os.getenv("MYSQL_URL")
    if mysql_url:
        if mysql_url.startswith("mysql://"):
            return mysql_url.replace("mysql://", "mysql+pymysql://", 1)
        return mysql_url

    mysql_host = os.getenv("MYSQL_HOST")
    mysql_user = os.getenv("MYSQL_USER")
    mysql_password = os.getenv("MYSQL_PASSWORD")
    mysql_db = os.getenv("MYSQL_DB")

    if not all([mysql_host, mysql_user, mysql_password, mysql_db]):
        return None

    mysql_port = os.getenv("MYSQL_PORT", "3306")
    return (
        f"mysql+pymysql://{quote_plus(mysql_user)}:"
        f"{quote_plus(mysql_password)}@{mysql_host}:{mysql_port}/"
        f"{quote_plus(mysql_db)}"
    )


def create_app(config_name="default"):
    app = Flask(__name__)

    # Limit uploads to 25 MB
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

    configure_logging(app)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    app.config.from_object(config_by_name[config_name])
    app.config["UPLOAD_FOLDER"] = str(app.config["UPLOAD_FOLDER"])
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # SECRET
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", app.config["SECRET_KEY"])

    # GOOGLE
    app.config["GOOGLE_CLIENT_ID"] = os.getenv("GOOGLE_CLIENT_ID")
    app.config["GOOGLE_CLIENT_SECRET"] = os.getenv("GOOGLE_CLIENT_SECRET")

    # DB
    database_uri = database_uri_from_env()
    if database_uri:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_uri

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # EXTENSIONS
    db.init_app(app)
    migrate.init_app(app, db)
    oauth.init_app(app)
    mail.init_app(app)

    app.logger.info(
        "SmartInsight startup: config=%s mail_server=%s mail_port=%s mail_timeout=%s "
        "mail_username_configured=%s mail_password_configured=%s "
        "mail_sender_configured=%s db_configured=%s secret_key_configured=%s",
        config_name,
        app.config.get("MAIL_SERVER"),
        app.config.get("MAIL_PORT"),
        app.config.get("MAIL_TIMEOUT"),
        bool(app.config.get("MAIL_USERNAME")),
        bool(app.config.get("MAIL_PASSWORD")),
        bool(app.config.get("MAIL_DEFAULT_SENDER")),
        bool(app.config.get("SQLALCHEMY_DATABASE_URI")),
        app.config.get("SECRET_KEY") != "dev-secret-key",
    )

    # GOOGLE OAUTH
    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    # BLUEPRINTS
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)

    # HOME
    @app.route("/")
    def home():
        return render_template("start.html")

    @app.route("/health")
    def health():
        mail_username = app.config.get("MAIL_USERNAME")
        mail_sender = app.config.get("MAIL_DEFAULT_SENDER")
        sender_email = parseaddr(mail_sender or "")[1]

        return jsonify({
            "status": "ok",
            "database_configured": bool(app.config.get("SQLALCHEMY_DATABASE_URI")),
            "mail_server": app.config.get("MAIL_SERVER"),
            "mail_port": app.config.get("MAIL_PORT"),
            "mail_timeout": app.config.get("MAIL_TIMEOUT"),
            "mail_username_configured": bool(mail_username),
            "mail_password_configured": bool(app.config.get("MAIL_PASSWORD")),
            "mail_sender_configured": bool(mail_sender),
            "mail_sender_matches_username": bool(
                mail_username
                and sender_email
                and sender_email.lower() == mail_username.lower()
            ),
            "secret_key_configured": app.config.get("SECRET_KEY") != "dev-secret-key",
        })

    # ERROR HANDLERS
    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(error):
        return render_template(
            "dashboard.html",
            error="File too large",
            max_upload_mb=app.config["MAX_UPLOAD_MB"],
        ), 413

    @app.errorhandler(Exception)
    def handle_error(error):
        if isinstance(error, HTTPException):
            return error

        app.logger.exception("Unhandled exception")
        return render_template(
            "dashboard.html",
            error="Unexpected error",
            max_upload_mb=app.config["MAX_UPLOAD_MB"],
        ), 500

    return app


app = create_app()
