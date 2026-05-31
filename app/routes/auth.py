from flask import Blueprint, request, session, redirect, url_for, render_template, current_app
from flask_mail import Message
from datetime import datetime
import random

from app.extensions import oauth, db, mail
from app.models.user import User

auth_bp = Blueprint("auth", __name__)


def auth_error(message: str, status_code: int = 500, exc: Exception | None = None):
    if exc is not None:
        current_app.logger.exception(message)
    else:
        current_app.logger.error(message)
    return render_template("verify.html", error=message), status_code


# =========================
# OTP GENERATOR
# =========================

def generate_otp():
    return str(random.randint(100000, 999999))


# =========================
# SEND OTP
# =========================

@auth_bp.route("/send-otp", methods=["POST"])
def send_otp():

    email = request.form.get("email")

    if not email:
        return auth_error("Please enter a valid email address.", 400)

    otp = generate_otp()

    # Save in session
    session["otp"] = otp
    session["email"] = email

    try:
        msg = Message(
            subject="SmartInsight OTP Verification",
            recipients=[email],
            body=f"Your SmartInsight OTP is: {otp}"
        )
        mail.send(msg)
    except Exception as exc:
        return auth_error(
            "Unable to send OTP right now. Please check your mail configuration and try again.",
            500,
            exc,
        )

    return redirect(url_for("auth.verify"))


# =========================
# VERIFY PAGE + OTP VERIFY
# =========================

@auth_bp.route("/verify", methods=["GET", "POST"])
def verify():

    # OPEN VERIFY PAGE
    if request.method == "GET":
        return render_template("verify.html")

    # VERIFY OTP
    entered_otp = request.form.get("otp")

    saved_otp = session.get("otp")
    email = session.get("email")

    if not email:
        return auth_error(
            "Session expired or email address not found. Please request a new OTP.",
            400,
        )

    if entered_otp == saved_otp:

        user = User.query.filter_by(email=email).first()

        if not user:
            user = User(
                name=email.split("@")[0].title(),
                email=email,
                auth_type="email",
                picture=None,
            )
            db.session.add(user)
        else:
            user.last_login = datetime.utcnow()

        db.session.commit()

        session["user"] = {
            "name": user.name,
            "email": user.email,
            "picture": user.picture,
            "auth_type": "email",
        }

        session["logged_in"] = True
        session.permanent = True

        return redirect(url_for("dashboard.index"))

    # ❌ WRONG OTP CASE
    return render_template(
        "verify.html",
        error="Invalid OTP"
    )


# =========================
# GOOGLE LOGIN
# =========================

@auth_bp.route("/login")
def login():

    if not current_app.config.get("GOOGLE_CLIENT_ID") or not current_app.config.get("GOOGLE_CLIENT_SECRET"):
        return auth_error(
            "Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
            500,
        )

    redirect_uri = url_for(
        "auth.authorize",
        _external=True,
    )

    return oauth.google.authorize_redirect(
        redirect_uri,
        prompt="select_account",

    )


@auth_bp.route("/authorize")
def authorize():
    try:
        token = oauth.google.authorize_access_token()
    except Exception as exc:
        return auth_error("Google authorization failed.", 500, exc)

    if not token:
        return auth_error("No token received from Google.", 500)

    # ✅ ONLY CORRECT WAY
    try:
        user_info = oauth.google.userinfo()
    except Exception as exc:
        return auth_error("Failed to fetch Google user info.", 500, exc)

    if not user_info:
        return auth_error("Google user info missing.", 500)

    email = user_info.get("email")
    name = user_info.get("name")
    picture = user_info.get("picture")

    if not email:
        return auth_error("Email not received from Google", 500)

    user = User.query.filter_by(email=email).first()

    if not user:
        user = User(
            name=name or email.split("@")[0],
            email=email,
            picture=picture,
            auth_type="google",
            last_login=datetime.utcnow(),
        )
        db.session.add(user)
    else:
        user.last_login = datetime.utcnow()

    db.session.commit()

    session.clear()
    session["logged_in"] = True
    session["user"] = {
        "name": user.name,
        "email": user.email,
        "picture": user.picture,
    }
    session.permanent = True
    return redirect(url_for("dashboard.index"))
# =========================
# LOGOUT
# =========================

@auth_bp.route("/logout")
def logout():

    session.clear()

    return redirect("/")