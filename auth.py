"""Flask-Login wiring: login manager, login/logout routes, password hashing.
Account creation itself happens in stripe_webhook.py, not here -- there is no
public signup route, since access is gated entirely by payment.
"""
from flask import Blueprint, redirect, render_template, request, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash

from db import User

login_manager = LoginManager()
login_manager.login_view = "auth.login"

auth_bp = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(db_email_ilike(email)).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.")
    return render_template("login.html")


def db_email_ilike(email):
    return User.email.ilike(email)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


def hash_password(plain_password):
    return generate_password_hash(plain_password)


if __name__ == "__main__":
    h = hash_password("temp-pw-123")
    assert check_password_hash(h, "temp-pw-123")
    assert not check_password_hash(h, "wrong")
    print("auth.py self-test passed")
