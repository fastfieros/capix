import logging
import json
from os import path

from flask import Flask, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from sqlalchemy.orm import sessionmaker
from datetime import datetime, MAXYEAR

from capix.views import setup
from capix.views import clients
from capix.views import filters
from capix.views import styles
from capix.views import frame

from capix.models import db
from capix.models.picture import Picture
from capix.models.tag import Tag
from capix.models.client import Client
from capix.models.filter import Filter
from capix.models.style import Style
from capix.models.config import Config

# Declare and initialize flask main app
app = Flask(__name__, 

    # Serve static files from the static subdirectory, when requests start with /static
    static_url_path="/static", static_folder="static",

    # Render and serve templates from the templates subdirectory
    template_folder="templates")


# Setup DB
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///pics.db"
db.app = app
db.init_app(app)
db.engine.execute("PRAGMA busy_timeout = 30000") # set 30 second timeout for db concurrency
Session = sessionmaker(bind=db.engine)

# Seems to check if it exists first.. XXX revisit if needed.
db.create_all()

# Setup config table (if exists)
with open(path.join(path.dirname(__file__), 'default_cfg.json'), 'r') as cfg_file:
    default_config = json.load(cfg_file)
    for k,v in default_config.items():
        if None == db.session.query(Config).filter(Config.key == k).one_or_none():
            cfg = Config(key=k, value=v)
            db.session.add(cfg)

with open(path.join(path.dirname(__file__), 'default_status.json'), 'r') as stat_file:
    default_status = json.load(stat_file)
    for k,v in default_status.items():
        cfg = db.session.query(Config).filter(Config.key == k).one_or_none()
        if None == cfg:
            cfg = Config(key=k, value=v)
        else:
            cfg.value = v

        db.session.add(cfg)

db.session.commit()

# Register blueprints here
app.register_blueprint(clients.bp)
app.register_blueprint(filters.bp)
app.register_blueprint(styles.bp)
app.register_blueprint(setup.bp)
app.register_blueprint(frame.bp)

# Set this for sessions (so far only needed for admin console to work)
app.config['SESSION_TYPE'] = "filesystem"
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/' #(Set the secret key to some random bytes. Keep this really secret!)

# Instead of disabling the cache, it will reload templates if the cached version no longer matches the template file.
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Setup admin console XXX DEBUGGING ONLY XXX TODO
admin = Admin(app, name='blarg', template_mode='bootstrap3')
admin.add_view(ModelView(Picture, db.session))
admin.add_view(ModelView(Tag, db.session))
admin.add_view(ModelView(Client, db.session))
admin.add_view(ModelView(Filter, db.session))
admin.add_view(ModelView(Style, db.session))
admin.add_view(ModelView(Config, db.session))

#Set default page to /clients
@app.route("/")
def index():
    return redirect("/clients", code=302)

logging.basicConfig(level=logging.DEBUG)
logging.getLogger().setLevel(logging.DEBUG)

##XXX: Insert defaults on first db build
default_filter = db.session.query(Filter).filter(Filter.name == 'Default').one_or_none()
if None == default_filter:
    default_filter = Filter(
        id=1,
        name="Default", 
        stars_bitfield=0x63, 
        date_min=datetime.utcfromtimestamp(0),
        date_max=datetime(MAXYEAR, 1, 1),
        enable_date=False,
        case_sensitive=True
    )
    db.session.add(default_filter)

default_style = db.session.query(Style).filter(Style.name == 'Default').one_or_none()
if None == default_style:
    default_style = Style(
        id=1,
        name="Default",
        caption_css="""
position:absolute;
bottom: 50px;
left: 100px;
text-shadow: 1px 1px 2px  #888;
font-size: 30px;
font-weight: bold;
-webkit-text-stroke: 1px #000;
color: #FFF;
font-family:'Lucida Sans', 'Lucida Sans Regular', 'Lucida Grande', 'Lucida Sans Unicode', Geneva, Verdana, sans-serif;
    """)
    db.session.add(default_style)

default_client = db.session.query(Client).filter(Client.name == 'Default').one_or_none()
if None == default_client:
    default_client = Client(
        id=1,
        name="Default", 
        shortname="default",
        animate_captions=True,
        animate_photos=True,
        display_seconds=60,
        filter=default_filter,
        style=default_style
    )
    db.session.add(default_client)


    db.session.commit()

##XXX TESTING ONLY
#bp_cfg = db.session.query(Config.value).filter_by(key="basepath").first()
#basepath = bp_cfg.value
#
#from capix.worker import add_all_pictures, delete_pictures
#logging.info("test db delete")
#delete_pictures()
#logging.info("test db build")
#add_all_pictures(basepath)
