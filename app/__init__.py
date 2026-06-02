from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus

from app.config import config_by_name
from app.extensions import db, migrate, oauth, mail
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()


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
        return jsonify({
            "status": "ok",
            "database_configured": bool(app.config.get("SQLALCHEMY_DATABASE_URI")),
            "mail_server": app.config.get("MAIL_SERVER"),
            "mail_port": app.config.get("MAIL_PORT"),
            "mail_username_configured": bool(app.config.get("MAIL_USERNAME")),
            "mail_password_configured": bool(app.config.get("MAIL_PASSWORD")),
            "mail_sender_configured": bool(app.config.get("MAIL_DEFAULT_SENDER")),
            "secret_key_configured": app.config.get("SECRET_KEY") != "dev-secret-key",
        })

    # ERROR HANDLERS
    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(error):
        return render_template("dashboard.html", error="File too large"), 413

    @app.errorhandler(Exception)
    def handle_error(error):
        app.logger.exception("Unhandled exception")
        return render_template("dashboard.html", error="Unexpected error"), 500

    return app


app = create_app()
