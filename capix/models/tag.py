from capix.models import db
from sqlalchemy.orm import relationship

from capix.models.relationships import filter_tags
from capix.models.relationships import picture_tags

class Tag(db.Model):
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.Text, nullable=False, unique=True)

    pictures = relationship('Picture',
                                secondary=picture_tags,
                                back_populates='tags')

    #filters = relationship('Filter',
    #                            secondary=filter_tags,
    #                            back_populates='tags')

    def __init__(self, tag):
        self.tag = tag

    def __repr__(self):
        return f"{self.tag}"