from sqlalchemy.orm import relationship

from capix.models import db
from capix.models.client import Client

class Style(db.Model):
    __tablename__ = 'styles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    caption_css = db.Column(db.Text)
    
    #clients = db.relationship('Client', backref='styles', lazy=True)
    clients = relationship('Client', back_populates="style")

    def __repr__(self):
        return f"{self.name}"


