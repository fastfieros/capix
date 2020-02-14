from flask import Flask, Blueprint, render_template, redirect, request, flash
from capix.models import db
from capix.models.client import Client
from capix.models.filter import Filter
from capix.models.style import Style
from capix.models.tag import Tag

from datetime import datetime, MAXYEAR
import logging
import json

bp = Blueprint('filters', __name__, url_prefix="/filters")

@bp.route("/")
def get_filters():
    all_filters = Filter.query.order_by(Filter.name)

    stars_checked = {}
    tag_lists = {}
    counts = {}

    for filt in all_filters:
        s = []
        if filt.stars_bitfield:
            for i in range(6):
                if 1<<i & filt.stars_bitfield:
                    s.append(i)
        stars_checked[filt.id] = s

        t = []
        if filt.tags:
            t = [ x.strip() for x in filt.tags.split(",") ]
        tag_lists[filt.id] = t

        q = filt.get_query()
        counts[filt.id] = q.count()

    realtags = json.dumps([ x[0] for x in db.session.query(Tag.tag).filter(Tag.pictures.any()).all() ])
    js_taglist = "var realtags=" + str(realtags) + ";"

    return render_template('filters.j2', 
        stars_checked=stars_checked,
        tag_lists=tag_lists,
        counts=counts,
        filters=all_filters,
        clients=Client.query.order_by(Client.name),
        js_taglist=js_taglist
        )


@bp.route("/add", methods=['POST'])
def add_filter():

    if request.form['name'] is "":
        flash("You forgot to specify the new filter's name", "Error")

    else:
        newfilter = Filter(
            name=request.form['name'],
            stars_bitfield=63,
            tags="",
            date_min=datetime.utcfromtimestamp(0),
            date_max=datetime(MAXYEAR, 1, 1),
            enable_date=False,
            case_sensitive=True
            )
        db.session.add(newfilter)
        db.session.commit()

    return redirect("/filters", code=302)


@bp.route("/remove/<int:cid>")
def remove_filter(cid):
    db.session.query(Filter).filter(Filter.id == cid).delete()
    db.session.commit()

    return redirect("/filters", code=302)


@bp.route("/update/<int:fid>", methods=['POST'])
def update_filter(fid):
    myfilter = db.session.query(Filter).filter(Filter.id == fid).one_or_none()
    if not myfilter:
        flash("Failed to find filter with specified id.", "Error")

    else:
        myfilter.stars_bitfield = request.form['stars_bitfield']
        myfilter.date_max = datetime.strptime(request.form['date_max'], '%Y-%m-%d')
        myfilter.date_min = datetime.strptime(request.form['date_min'], '%Y-%m-%d')
        myfilter.case_sensitive = request.form.get('case-sensitive') != None
        myfilter.enable_date = request.form.get('filter-date') != None
        db.session.commit()

    return redirect("/filters", code=302)


@bp.route("/addtag/<int:fid>", methods=['POST'])
def add_tag(fid):
    myfilter = db.session.query(Filter).filter(Filter.id == fid).one_or_none()
    if not myfilter:
        flash("Failed to find filter with specified id.", "Error")

    else:
        tag = request.form['tag'].strip()
        oldtags = myfilter.tags
        if oldtags:
            taga = oldtags.split(",")
            if tag not in taga:
                taga.append(tag)
                newtags = ",".join(taga)
                myfilter.tags = newtags
                db.session.commit()
        else:
            myfilter.tags = tag
            db.session.commit()

    return redirect("/filters", code=302)


@bp.route("/removetag/<int:fid>/<int:tid>")
def update_client_remove_tag(fid, tid):
    myfilter = db.session.query(Filter).filter(Filter.id == fid).one_or_none()
    if not myfilter:
        flash("Failed to find filter with specified id.", "Error")

    else:
        oldtags = myfilter.tags
        if oldtags:
            taga = oldtags.split(",")
            taga.pop(tid)
            newtags = ",".join(taga)
            myfilter.tags = newtags
            db.session.commit()

    return redirect("/filters", code=302)