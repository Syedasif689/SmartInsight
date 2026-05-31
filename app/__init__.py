from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus

from app.config import config_by_name
from app.extensions import db, migrate, oauth, mail
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()


def create_app(config_name="default"):
    app = Flask(__name__)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    app.config.from_object(config_by_name[config_name])
    app.config["UPLOAD_FOLDER"] = str(app.config["UPLOAD_FOLDER"])

    # SECRET
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", app.config["SECRET_KEY"])

    # GOOGLE
    app.config["GOOGLE_CLIENT_ID"] = os.getenv("GOOGLE_CLIENT_ID")
    app.config["GOOGLE_CLIENT_SECRET"] = os.getenv("GOOGLE_CLIENT_SECRET")

    # DB
    mysql_url = os.getenv("MYSQL_URL")
    if mysql_url:
        if mysql_url.startswith("mysql://"):
            mysql_url = mysql_url.replace("mysql://", "mysql+pymysql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = mysql_url

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