from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

from capix.models import db


class Client(db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    shortname = db.Column(db.String, nullable=False)
    animate_captions = db.Column(db.Boolean)
    animate_photos = db.Column(db.Boolean)
    display_seconds = db.Column(db.Integer)

    # many to many picture <=> tag
    filter_id = db.Column(db.Integer, db.ForeignKey('filters.id'))
    filter = relationship('Filter', back_populates='clients')

    style_id = db.Column(db.Integer, db.ForeignKey('styles.id'))
    style = relationship('Style', back_populates='clients')

    def __repr__(self):
        return f"{self.name} [{self.shortname}]"


