from flask import Blueprint, request, session, redirect, url_for, render_template, current_app
from flask_mail import Message
from datetime import datetime
import random

from app.extensions import oauth, db, mail
from app.models.user import User

auth_bp = Blueprint("auth", __name__)


def mask_email(email: str) -> str:
    if "@" not in email:
        return "***"

    name, domain = email.split("@", 1)
    visible = name[:2] if len(name) > 2 else name[:1]
    return f"{visible}***@{domain}"


def auth_error(message: str, status_code: int = 500, exc: Exception | None = None):
    if exc is not None:
        current_app.logger.exception(message)
    else:
        current_app.logger.error(message)
    return render_template("verify.html", error=message), status_code


def mail_error_detail(exc: Exception) -> str:
    smtp_error = getattr(exc, "smtp_error", None)
    if isinstance(smtp_error, bytes):
        smtp_error = smtp_error.decode("utf-8", errors="replace")

    if smtp_error:
        return f"{type(exc).__name__}: {smtp_error}"

    return f"{type(exc).__name__}: {exc}"


def otp_error(message: str, exc: Exception | None = None):
    if exc is not None:
        current_app.logger.exception("[OTP] %s detail=%s", message, mail_error_detail(exc))
    else:
        current_app.logger.error("[OTP] %s", message)
    return render_template(
        "verify.html",
        error=message,
        error_detail=mail_error_detail(exc) if exc else None,
    ), 200


# =========================
# OTP GENERATOR
# =========================

def generate_otp():
    return str(random.randint(100000, 999999))


def login_user(user: User, auth_type: str):
    session.clear()
    session["logged_in"] = True
    session["user"] = {
        "name": user.name,
        "email": user.email,
        "picture": user.picture,
        "auth_type": auth_type,
    }
    session.permanent = True


# =========================
# SEND OTP
# =========================

@auth_bp.route("/send-otp", methods=["GET"])
def send_otp_page():
    current_app.logger.info("[OTP] GET /send-otp redirected to dashboard")
    return redirect(url_for("dashboard.index"))


@auth_bp.route("/send-otp", methods=["POST"])
def send_otp():

    email = (request.form.get("email") or "").strip().lower()
    current_app.logger.info(
        "[OTP] POST /send-otp received email=%s remote_addr=%s",
        mask_email(email),
        request.headers.get("X-Forwarded-For", request.remote_addr),
    )

    if not email:
        return otp_error("Please enter a valid email address.")

    sender = current_app.config.get("MAIL_DEFAULT_SENDER")
    current_app.logger.info(
        "[OTP] mail config mail_server=%s mail_port=%s mail_tls=%s "
        "username_configured=%s password_configured=%s sender_configured=%s",
        current_app.config.get("MAIL_SERVER"),
        current_app.config.get("MAIL_PORT"),
        current_app.config.get("MAIL_USE_TLS"),
        bool(current_app.config.get("MAIL_USERNAME")),
        bool(current_app.config.get("MAIL_PASSWORD")),
        bool(sender),
    )

    if not sender:
        return otp_error(
            "Email login is not configured yet. Please set MAIL_USERNAME, MAIL_PASSWORD, and MAIL_DEFAULT_SENDER on Render."
        )

    otp = generate_otp()

    # Save in session
    session["otp"] = otp
    session["email"] = email

    try:
        current_app.logger.info(
            "[OTP] sending message email=%s sender=%s",
            mask_email(email),
            sender,
        )
        msg = Message(
            subject="SmartInsight OTP Verification",
            sender=sender,
            recipients=[email],
            body=f"Your SmartInsight OTP is: {otp}"
        )
        mail.send(msg)
        current_app.logger.info("[OTP] mail.send succeeded email=%s", mask_email(email))
    except Exception as exc:
        return otp_error(
            "Unable to send OTP right now. Please check your mail configuration and try again.",
            exc,
        )

    current_app.logger.info("[OTP] redirecting to verify email=%s", mask_email(email))
    return redirect(url_for("auth.verify"))


# =========================
# VERIFY PAGE + OTP VERIFY
# =========================

@auth_bp.route("/verify", methods=["GET", "POST"])
def verify():

    # OPEN VERIFY PAGE
    if request.method == "GET":
        current_app.logger.info(
            "[OTP] GET /verify has_email_in_session=%s has_otp_in_session=%s",
            bool(session.get("email")),
            bool(session.get("otp")),
        )
        return render_template("verify.html")

    # VERIFY OTP
    entered_otp = request.form.get("otp")

    saved_otp = session.get("otp")
    email = session.get("email")
    current_app.logger.info(
        "[OTP] POST /verify email=%s has_saved_otp=%s entered_otp_length=%s",
        mask_email(email or ""),
        bool(saved_otp),
        len(entered_otp or ""),
    )

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

        login_user(user, "email")
        current_app.logger.info("[OTP] verification succeeded email=%s", mask_email(email))

        return redirect(url_for("dashboard.index"))

    # ❌ WRONG OTP CASE
    current_app.logger.warning("[OTP] invalid OTP email=%s", mask_email(email or ""))
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

    login_user(user, "google")
    return redirect(url_for("dashboard.index"))
# =========================
# LOGOUT
# =========================

@auth_bp.route("/logout")
def logout():

    session.clear()

    return redirect("/")
