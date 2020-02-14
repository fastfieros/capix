from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from capix.models import db
from capix.models.relationships import filter_tags

from capix.models.client import Client
from capix.models.picture import Picture
from capix.models.tag import Tag

class Filter(db.Model):
    __tablename__ = 'filters'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    stars_bitfield = db.Column(db.Integer)
    date_min = db.Column(db.DateTime)
    date_max = db.Column(db.DateTime)
    case_sensitive = db.Column(db.Boolean)
    enable_date = db.Column(db.Boolean)

    #clients = db.relationship('Client', backref='filters', lazy=True)
    clients = db.relationship('Client', back_populates='filter')

    # many to many picture <=> tag
    #tags = relationship('Tag',
    #                    secondary=filter_tags,
    #                    back_populates='filters')

    # Not using the many-to-many relationship here as we want the 
    #  user to be able to specify tags that don't exist yet on any picture,
    #  or to keep tags in the filter after all pictures containing that 
    #  tag have been updated. In short, we want the user to have unfettered
    #  control of the tag list here, though we will suggest to them tags
    #  that are associated w/ exiting pictures to help them out. 
    tags = db.Column(db.String)

    def get_query(self):
        # Start w/ query all pictures
        q = db.session.query(Picture)

        # Add date filters
        if self.enable_date:
            q = q.filter(Picture.taken >= self.date_min)
            q = q.filter(Picture.taken <= self.date_max)

        # Don't filter if we're looking for *any* star value
        if self.stars_bitfield != 63: 
            stars_list = [ i for i in range(6) if 1<<i & self.stars_bitfield ]
            q = q.filter(Picture.stars.in_(stars_list)) \

        # Don't filter tags if none are specified.
        if self.tags:
            tag_list = self.tags.split(",")
            q = q.join(Picture.tags).filter(Tag.id.in_(
                db.session.query(Tag.id).filter(Tag.tag.in_(tag_list))
            ))
        
        return q


    def __repr__(self):
        stars_arr = []
        if self.stars_bitfield:
            for i in range(5):
                if self.stars_bitfield & (1<<i):
                    stars_arr.append(i)

        stars_str = ",".join([str(x) for x in stars_arr])
        return f"{self.name}, tags {self.tags}, stars:{stars_str}, dates '{self.date_min}'-'{self.date_max}'"


