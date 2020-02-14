from flask import Flask, Blueprint, render_template, redirect, request, flash
from capix.models import db
from capix.models.client import Client
from capix.models.filter import Filter
from capix.models.style import Style
import logging

bp = Blueprint('clients', __name__, url_prefix="/clients")

def shortname_is_unique(sn):
    return None == db.session.query(Client).filter(Client.shortname == sn).one_or_none()


@bp.route("/")
def get_clients():
    return render_template('clients.j2', 
        styles=Style.query.order_by(Style.name),
        filters=Filter.query.order_by(Filter.name),
        clients=Client.query.order_by(Client.name)
        )


@bp.route("/add", methods=['POST'])
def add_client():

    # Ensure unque shortname
    if not shortname_is_unique(request.form['shortname']):
        flash("Could not add new client because a client with that id already exists!", "Error")
    elif request.form['shortname'] is "":
        flash("You forgot to specify the new client's id", "Error")
    elif request.form['name'] is "":
        flash("You forgot to specify the new client's name", "Error")
    else:
        newclient = Client(
            shortname=request.form['shortname'],
            name=request.form['name'],
            filter=db.session.query(Filter).first(),
            style=db.session.query(Style).first(),
            display_seconds=600
            )
        db.session.add(newclient)
        db.session.commit()

    return redirect("/clients", code=302)


@bp.route("/remove/<int:cid>", methods=['POST'])
def remove_client(cid):
    db.session.query(Client).filter(Client.id == cid).delete()
    db.session.commit()

    return redirect("/clients", code=302)


@bp.route("/update/<int:cid>", methods=['POST'])
def update_client(cid):
    client = db.session.query(Client).filter(Client.id == cid).one_or_none()
    myfilter = db.session.query(Filter).filter(Filter.id == request.form['filter_id']).one_or_none()
    mystyle = db.session.query(Style).filter(Style.id == request.form['style_id']).one_or_none()
    if not client or not myfilter or not mystyle:
        flash("Failed to find client, filter, or style with specified id.", "Error")

    else:
        if client.shortname != request.form['shortname']:
            if not shortname_is_unique(request.form['shortname']):
                flash("Could not change id because a client with that id already exists!", "Error")
            elif request.form['shortname'] is "":
                flash("Can not change id to nothing!", "Error")
            else:
                client.shortname = request.form['shortname']

        client.filter = myfilter
        client.style = mystyle
        client.animate_captions = request.form.get('anim-cap') != None
        client.animate_photos = request.form.get('anim-photo') != None
        client.display_seconds = request.form.get('display_seconds')

        db.session.commit()

    return redirect("/clients", code=302)


# TODO:
# - (re)Generate DB
# - show stats
