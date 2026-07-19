import logging

import stripe
from flask import Flask, redirect, render_template, url_for
from flask_login import current_user, login_required

import config
from auth import auth_bp, login_manager
from db import db
from lessons_config import LESSONS, get_lesson, youtube_embed_url
from storage import get_pdf_url, StorageError
from stripe_webhook import stripe_bp

logging.basicConfig(level=logging.INFO)


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    stripe.api_key = config.STRIPE_SECRET_KEY

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(stripe_bp)

    with app.app_context():
        db.create_all()  # no-op against Supabase once schema.sql has been applied there

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("auth.login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html", lessons=LESSONS)

    @app.route("/lesson/<int:lesson_id>")
    @login_required
    def lesson(lesson_id):
        lesson_data = get_lesson(lesson_id)
        if not lesson_data:
            return redirect(url_for("dashboard"))

        embed_url = (
            youtube_embed_url(lesson_data["youtube_id"]) if lesson_data["youtube_id"] else None
        )

        pdf_url = None
        storage_error = None
        try:
            pdf_url = get_pdf_url(lesson_data)
        except StorageError as exc:
            storage_error = str(exc)

        return render_template(
            "lesson.html",
            lesson=lesson_data,
            embed_url=embed_url,
            pdf_url=pdf_url,
            storage_error=storage_error,
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
