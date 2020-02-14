from sqlalchemy import Table, ForeignKey
from sqlalchemy.orm import relationship

from capix.models import db

picture_tags = Table('picture_tags', db.metadata,
    db.Column('picture_id', ForeignKey('pictures.id'), primary_key=True),
    db.Column('tag_id', ForeignKey('tags.id'), primary_key=True)
    )

filter_tags = Table('filter_tags', db.metadata,
    db.Column('filter_id', ForeignKey('filters.id'), primary_key=True),
    db.Column('tag_id', ForeignKey('tags.id'), primary_key=True)
    )

