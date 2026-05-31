from flask import (
    Blueprint, request, session, redirect,
    url_for, render_template, current_app
)
from flask_mail import Message
from datetime import datetime
import random

from app.extensions import oauth, db, mail
from app.models.user import User

auth_bp = Blueprint("auth", __name__)


# =========================================================
# ERROR HANDLER (clean + reusable)
# =========================================================
def auth_error(message: str, status_code: int = 500, exc: Exception | None = None):
    if exc:
        current_app.logger.exception(message)
    else:
        current_app.logger.error(message)

    return render_template("verify.html", error=message), status_code


# =========================================================
# OTP GENERATION
# =========================================================
def generate_otp():
    return str(random.randint(100000, 999999))


# =========================================================
# SEND OTP
# =========================================================
@auth_bp.route("/send-otp", methods=["POST"])
def send_otp():

    email = request.form.get("email", "").strip()

    if not email:
        return auth_error("Email is required", 400)

    otp = generate_otp()

    # safer session handling
    session["otp"] = otp
    session["pending_email"] = email
    session["otp_verified"] = False

    try:
        msg = Message(
            subject="SmartInsight OTP Verification",
            recipients=[email],
            body=f"Your OTP is: {otp}"
        )
        mail.send(msg)

    except Exception as exc:
        return auth_error(
            "Failed to send OTP. Check mail configuration.",
            500,
            exc
        )

    return redirect(url_for("auth.verify"))


# =========================================================
# VERIFY OTP
# =========================================================
@auth_bp.route("/verify", methods=["GET", "POST"])
def verify():

    if request.method == "GET":
        return render_template("verify.html")

    entered_otp = request.form.get("otp", "").strip()

    saved_otp = session.get("otp")
    email = session.get("pending_email")

    if not email or not saved_otp:
        return auth_error("OTP expired. Please try again.", 400)

    if entered_otp != saved_otp:
        return render_template("verify.html", error="Invalid OTP")

    # get or create user
    user = User.query.filter_by(email=email).first()

    if not user:
        user = User(
            name=email.split("@")[0].title(),
            email=email,
            auth_type="email",
            picture=None,
            last_login=datetime.utcnow(),
        )
        db.session.add(user)
    else:
        user.last_login = datetime.utcnow()

    db.session.commit()

    # clear OTP session
    session.pop("otp", None)
    session.pop("pending_email", None)

    # login session
    session["user"] = {
        "name": user.name,
        "email": user.email,
        "picture": user.picture,
        "auth_type": "email",
    }

    session["otp_verified"] = True
    session.permanent = True

    return redirect(url_for("dashboard.index"))


# =========================================================
# GOOGLE LOGIN
# =========================================================
@auth_bp.route("/login")
def login():

    if not current_app.config.get("GOOGLE_CLIENT_ID") or not current_app.config.get("GOOGLE_CLIENT_SECRET"):
        return auth_error(
            "Google OAuth not configured in environment variables.",
            500,
        )

    redirect_uri = url_for("auth.authorize", _external=True)

    return oauth.google.authorize_redirect(
        redirect_uri,
        prompt="select_account"
    )


# =========================================================
# GOOGLE AUTHORIZE CALLBACK
# =========================================================
@auth_bp.route("/authorize")
def authorize():

    try:
        token = oauth.google.authorize_access_token()
    except Exception as exc:
        return auth_error("Google login failed", 500, exc)

    user_info = token.get("userinfo") or {}

    email = user_info.get("email")
    if not email:
        return auth_error("Google did not return email", 500)

    name = user_info.get("name") or email.split("@")[0].title()
    picture = user_info.get("picture")

    user = User.query.filter_by(email=email).first()

    if not user:
        user = User(
            name=name,
            email=email,
            picture=picture,
            auth_type="google",
            last_login=datetime.utcnow(),
        )
        db.session.add(user)
    else:
        user.last_login = datetime.utcnow()

    db.session.commit()

    session["user"] = {
        "name": user.name,
        "email": user.email,
        "picture": user.picture,
        "auth_type": "google",
    }

    session.permanent = True

    return redirect(url_for("dashboard.index"))


# =========================================================
# LOGOUT
# =========================================================
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))