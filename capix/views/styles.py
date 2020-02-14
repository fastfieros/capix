from flask import Flask, Blueprint, render_template, redirect, request, flash
from capix.models import db
from capix.models.style import Style

import logging

bp = Blueprint('styles', __name__, url_prefix="/styles")

@bp.route("/")
def get_styles():
    all_styles = Style.query.order_by(Style.name)

    return render_template('styles.j2', 
        styles=all_styles
        )


@bp.route("/add", methods=['POST'])
def add_style():

    if request.form['name'] is "":
        flash("You forgot to specify the new style's name", "Error")

    else:
        newstyle = Style(
            name=request.form['name']
            )
        db.session.add(newstyle)
        db.session.commit()

    return redirect("/styles", code=302)


@bp.route("/remove/<int:sid>")
def remove_style(sid):
    db.session.query(Style).filter(Style.id == sid).delete()
    db.session.commit()

    return redirect("/styles", code=302)


@bp.route("/update/<int:sid>", methods=['POST'])
def update_style(sid):
    mystyle = db.session.query(Style).filter(Style.id == sid).one_or_none()
    if not mystyle:
        flash("Failed to find style with specified id.", "Error")

    else:
        mystyle.caption_css = request.form['css']
        db.session.commit()

    return redirect("/styles", code=302)

