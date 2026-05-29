from flask import Blueprint, request, session, redirect, url_for, render_template
from flask_mail import Message
from datetime import datetime
import random

from app.extensions import oauth, db, mail
from app.models.user import User

auth_bp = Blueprint("auth", __name__)

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

    otp = generate_otp()

    # Save in session
    session["otp"] = otp
    session["email"] = email

    # Send mail
    msg = Message(
        subject="SmartInsight OTP Verification",
        recipients=[email],
        body=f"Your SmartInsight OTP is: {otp}"
    )

    mail.send(msg)

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

    if entered_otp == saved_otp:

        user = User.query.filter_by(email=email).first()

        if not user:
            user = User(
                name=email.split("@")[0].title(),
                email=email,
                auth_type="email",
                picture=None
            )
            db.session.add(user)
        else:
            user.last_login = datetime.utcnow()

        db.session.commit()

        session["user"] = {
            "name": user.name,
            "email": user.email,
            "picture": user.picture,
            "auth_type": "email"
        }

        session["logged_in"] = True

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

    redirect_uri = url_for(
        "auth.authorize",
        _external=True
    )

    return oauth.google.authorize_redirect(
        redirect_uri,
        prompt="select_account"
    )


@auth_bp.route("/authorize")
def authorize():

    token = oauth.google.authorize_access_token()

    user_info = token.get("userinfo")

    email = user_info["email"]

    user = User.query.filter_by(email=email).first()

    if not user:

        user = User(
            name=user_info["name"],
            email=email,
            picture=user_info["picture"],
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
    }

    session["logged_in"] = True

    return redirect("/")


# =========================
# LOGOUT
# =========================

@auth_bp.route("/logout")
def logout():

    session.clear()

    return redirect("/")