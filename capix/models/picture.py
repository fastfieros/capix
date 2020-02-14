import os
import logging
import json

from PIL import Image, ExifTags
from sqlalchemy.orm import relationship

from capix.models import db
from capix.models.relationships import picture_tags
from capix.models.config import Config

from flask import current_app as app

class Picture(db.Model):
    __tablename__ = 'pictures'

    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String, nullable=False)
    views = db.Column(db.Integer)
    dirty = db.Column(db.Integer)
    stars = db.Column(db.Integer)
    title = db.Column(db.Text)
    description = db.Column(db.Text)
    mtime = db.Column(db.Integer)
    taken = db.Column(db.DateTime)

    # many to many picture <=> tag
    tags = relationship('Tag',
                        secondary=picture_tags,
                        back_populates='pictures')

    def __init__(self, path, tags, mtime, stars, title, description, taken):
        self.path = path
        self.views = 0
        self.dirty = 0
        self.tags = tags
        self.stars = stars
        self.title = title
        self.description = description
        self.mtime = mtime
        self.taken = taken


    def __repr__(self):
        return f"{self.path}"

    def get_json(self):
        return json.dumps({
            'id':self.id, 
            'stars':self.stars, 
            'title':self.title, 
            'description':self.description,
            'mtime':str(self.mtime),
            'taken':self.taken and self.taken.strftime("%Y/%m/%d") or None,
            'views':self.views,
            })


    def get_fullpath(self):
        bp_cfg = db.session.query(Config.value).filter_by(key="basepath").first()
        basepath = bp_cfg.value
        path = self.path
        if path[0] is '/':
            path = path[1:]

        return os.path.normpath(os.path.join(basepath, path))


    def rotate_by_exif(self, image):
        try:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation]=='Orientation':
                    break
            exif=dict(image._getexif().items())

            if exif[orientation] == 3:
                image=image.rotate(180, expand=True)
            elif exif[orientation] == 6:
                image=image.rotate(270, expand=True)
            elif exif[orientation] == 8:
                image=image.rotate(90, expand=True)

        except (AttributeError, KeyError, IndexError):
            # cases: image don't have getexif
            pass

        return image


    def get_thumbnail(self, size = (128,128)):

        im = Image.open(self.get_fullpath())
        im.thumbnail(size, Image.ANTIALIAS)

        return self.rotate_by_exif(im)

