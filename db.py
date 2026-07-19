"""SQLAlchemy models + engine. Targets Supabase Postgres in production via
config.DATABASE_URL; falls back to a local sqlite file when that env var
isn't set, so the app boots without real Supabase credentials.
"""
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "portal_users"

    # Integer (not BigInteger) so sqlite's ROWID-alias autoincrement works
    # for local dev; Postgres/Supabase still assigns via schema.sql's own
    # `bigint generated always as identity`, independent of this Python type.
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.Text, nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    name = db.Column(db.Text)
    is_enrolled = db.Column(db.Boolean, nullable=False, default=True)
    stripe_customer_id = db.Column(db.Text)
    stripe_checkout_session = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Flask-Login expects these on the user object.
    @property
    def is_active(self):
        return self.is_enrolled

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)
