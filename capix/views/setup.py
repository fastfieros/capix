from flask import Flask, Blueprint, render_template, redirect, request, flash
from flask import current_app as app

from capix.models import db
from capix.models.client import Client
from capix.models.filter import Filter
from capix.models.style import Style
from capix.models.config import Config
from capix.worker import add_all_pictures, delete_pictures

import logging
import json
import os
from datetime import datetime

bp = Blueprint('setup', __name__, url_prefix="/setup")

def get_status_info():
    count_row = db.session.query(Config.value).filter(Config.key == "count").one_or_none()
    done_row = db.session.query(Config.value).filter(Config.key == "done").one_or_none()
    rbs_row = db.session.query(Config.value).filter(Config.key == "rebuild_start").one_or_none()
    rbe_row = db.session.query(Config.value).filter(Config.key == "rebuild_end").one_or_none()
    rebuilding_row = db.session.query(Config.value).filter(Config.key == "rebuilding").one_or_none()
    bp_row = db.session.query(Config.value).filter_by(key="basepath").one_or_none()

    end_time = None
    if rbe_row.value:
        end_time = datetime.fromtimestamp(float(rbe_row.value))

    start_time = None
    if rbs_row.value:
        start_time = datetime.fromtimestamp(float(rbs_row.value))

    count = None
    if count_row:
        count = count_row.value

    done = None
    if done_row:
        done = done_row.value

    rebuilding = None
    if rebuilding_row:
        rebuilding = rebuilding_row.value
    
    delta = None
    if start_time:
        if end_time:
            d = end_time - start_time
        else:
            d = datetime.utcnow() - start_time

        delta = round(d.total_seconds())

    dbsize = os.path.getsize(bp_row.value)

    return {
        "count":count,
        "done":done, 
        "end":end_time and end_time.strftime("%H:%M %Y/%m%/%d") or None, 
        "start":start_time and start_time.strftime("%H:%M %Y/%m%/%d") or None, 
        "delta":delta,
        "rebuilding":rebuilding,
        "dbsize":dbsize
        }

@bp.route("/dbstatus")
def database_status():
    return json.dumps(get_status_info())


@bp.route("/start_rebuild", methods=["POST"])
def rebuild_database():
    bp_row = db.session.query(Config.value).filter_by(key="basepath").first()
    rebuilding_row = db.session.query(Config.value).filter_by(key="rebuilding").first()

    logging.info("db delete")
    delete_pictures()

    logging.info("db build")
    add_all_pictures(bp_row.value)

    return redirect("/setup/status", code=302)


@bp.route("/status")
def show_status():
    bp_row = db.session.query(Config.value).filter_by(key="basepath").first()
    rebuilding_row = db.session.query(Config.value).filter_by(key="rebuilding").first()
    rebuild_start_row = db.session.query(Config.value).filter_by(key="rebuild_start").first()

    return render_template('setup.j2', 
        path=bp_row.value,
        rebuilding=rebuilding_row.value,
        rebuild_start=rebuild_start_row.value,
        status=get_status_info()
    )


@bp.route("/")
def index():
    return redirect("/status", code=302)


# TODO:
# - (re)Generate DB
# - show stats
