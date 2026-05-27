from app.extensions import db
from datetime import datetime

class Dataset(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    filename = db.Column(db.String(255))
    filepath = db.Column(db.String(500))

    user_email = db.Column(db.String(150))

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)