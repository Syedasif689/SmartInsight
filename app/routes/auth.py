from flask import Blueprint, redirect, url_for, session
from app.extensions import oauth, db
from app.models.user import User
from datetime import datetime

auth_bp = Blueprint("auth", __name__)


# LOGIN
@auth_bp.route("/login")
def login():
    redirect_uri = url_for("auth.authorize", _external=True)
    return oauth.google.authorize_redirect(
    redirect_uri,
    prompt="select_account"
)

# GOOGLE CALLBACK
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

    return redirect("/")


# LOGOUT
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/")