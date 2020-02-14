from flask import Flask, Blueprint, render_template, redirect, request, send_file, make_response
from capix.models import db
from capix.models.picture import Picture
from capix.models.client import Client
from capix.models.filter import Filter
from capix.models.tag import Tag
from capix.models.style import Style
from sqlalchemy.sql import func

from PIL import Image

import json
import logging
import os
import io

bp = Blueprint('frame', __name__, url_prefix="/frame")

@bp.route("/<shortname>")
def get_default(shortname):
    myclient = db.session.query(Client).filter(Client.shortname == shortname).one_or_none()
    if not myclient:
        return json.dumps({"error":f"No client id, '{shortname}'"})

    return render_template('frame.j2', 
        status_timeout=30*1000,
        picture_timeout=myclient.display_seconds * 1000,
        shortname=shortname,
        frame_style=myclient.style.caption_css
        )



@bp.route("/<shortname>/next.json")
def get_frame(shortname):
    myclient = db.session.query(Client).filter(Client.shortname == shortname).one_or_none()
    if not myclient:
        ret = json.dumps({"error":f"No client id, '{shortname}'"})

    pf = myclient.filter

    q = pf.get_query()
    pic = q.order_by(func.random()).first()
    if pic:
        pic.views += 1
        db.session.commit()

        ret = pic.get_json()
    else:
        ret = json.dumps({"error":f"No pictures matched filter, '{pf.name}'"})

    r = make_response(ret, 200, 
        {
            'content-type': 'text/json', 
            "Cache-Control": "no-cache"
        })
    return r



@bp.route("/picture/<int:pid>.jpg")
def get_picture(pid):

    mypic = db.session.query(Picture).filter(Picture.id == pid).one_or_none()
    if not mypic:
        r = make_response("{error:no picture}", 200, 
            {'content-type': 'text/json', "Cache-Control": "no-cache"}
            )
        return r


    w = request.args.get("w") 
    h = request.args.get("h") 
    if w and h:
        resize = (int(w),int(h))
        im = mypic.get_thumbnail(resize)

        bio = io.BytesIO()
        im.save(bio, format="jpeg")
        response = make_response(bio.getvalue())
        response.headers.set('Content-Type', 'image/jpeg')
        return response

    else:
        return send_file(mypic.get_fullpath())