from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

from capix.models import db

class Config(db.Model):
    __tablename__="config"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String, nullable=False, unique=True)
    value = db.Column(db.String, nullable=True)

    def __repr__(self):
        return f"{self.key}: {self.value}\n"
