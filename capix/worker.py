#Processing
#from multiprocessing import Process, Queue, current_process, freeze_support, Event
# NOTE: Process-based parallelization has issues due to sqlite backend not handling multiple processes accessing the db well (frequently timesout due to locked database). Also there seems to be some kind of shared memory still being passed to the child processes even after disposing the engine and re-creating the session - segfualts observed around 30% of debug runs. Conclusion - use threading based parallelism until we have a good reason to use processes instead.

#Threading
from threading import Thread, Event, current_thread, Lock 
from queue import Queue

from queue import Empty
import logging
import fs
import os
from random import randint
from os.path import basename , getmtime
from time import sleep
from datetime import datetime
from PIL import Image, UnidentifiedImageError

#from capix import Session
from capix.models import db
from capix.models.picture import Picture
from capix.models.tag import Tag
from capix.models.config import Config
from capix.models.relationships import picture_tags, filter_tags
from sqlalchemy.exc import IntegrityError, OperationalError 

from capix.py_avm import AVM
from capix.py_avm.exceptions import NoXMPPacketFound

logging.basicConfig()

def process_picture(basepath, path):

    fpath = os.path.normpath(f"{basepath}/{path}")
    stars = 0
    title = ""
    description = ""
    tags = []
    mtime = None
    taken = None

    if not os.path.exists(fpath):
        logging.error(f"{fpath} does not exist!")
        return (None, None)

    try:
        avm = AVM.from_image(fpath)

        if avm.Rating and avm.Rating > 0:
            stars = avm.Rating

        if avm.Title:
            title = avm.Title

        if avm.Description:
            description = avm.Description

        if avm.Subject.Name and len(avm.Subject.Name):
            tags = avm.Subject.Name

    except (NoXMPPacketFound, ValueError):
        logging.warning("{} has no XMP data.".format(fpath))

    # Store file modified time
    mtime = getmtime(fpath)

    # Store EXIF date taken (first match of the following 3 tags)
    dT = None
    try:
        im = Image.open(fpath)
        exif = im.getexif()
        TTags=[(36867,37521), #TTags=[('DateTimeOriginal','SubsecTimeOriginal'),#when img taken
            (36868,37522),    #    ('DateTimeDigitized','SubsecTimeDigitized'),#when img stored digitally
            (306,37520)]      #    ('DateTime','SubsecTime')]#when img file was changed
        for i in TTags:
            dT, sub = exif.get(i[0]), exif.get(i[1],0)
            dT = dT[0] if type(dT) == tuple else dT #PILLOW 3.0 returns tuples now
            sub = sub[0] if type(sub) == tuple else sub
            if dT != None:
                #got valid time
                break

    except UnidentifiedImageError:
        logging.warning(f"PIL couldn't read image: {fpath}.")

    if dT:
        # found time tags
        datetimestring = '{}.{}'.format(dT,sub)
        if datetimestring == '0000:00:00 00:00:00.0':
            pass
        else:
            T = datetime.strptime(datetimestring,'%Y:%m:%d %H:%M:%S.%f')
            taken = T

    newpic = Picture(path=path, tags=[], mtime=mtime, stars=stars, title=title, description=description, taken=taken)
    return tags, newpic


def add_picture(ses, basepath, path, dbl):

    tags, newpic = process_picture(basepath, path)
    if newpic:
        dbl.acquire()

        db_tags = []
        for t in tags:
            existing_tag = Tag.query.filter_by(tag=t).one_or_none()
            if existing_tag:
                # add the existing one (db enforces unique, so there should only be one)
                newtag = existing_tag
            else:
                # Make a new one
                newtag = Tag(t)
                db.session.add(newtag)

            db_tags.append(newtag)

        newpic.tags = db_tags
        ses.add(newpic)
        ses.commit()

        dbl.release()

    logging.info(f"Processed picture: {path}")


def delete_pictures():

    db.engine.execute(picture_tags.delete())
    db.engine.execute(filter_tags.delete())

    Picture.query.delete()
    Tag.query.delete()

    count_row = db.session.query(Config).filter(Config.key == "count").one_or_none()
    count_row.value = "0"

    done_row = db.session.query(Config).filter(Config.key == "done").one_or_none()
    done_row.value = "0"

    db.session.commit()


def mp_worker(taskq, doneq, dbl):
    #must be called ASAP in new processes to prevent sharing engine pools
    #db.engine.dispose()
    #must be called in new processes to prevent sharing db sessions
    #session = Session()
    #flask-sqlalchemy uses scopedsession, so the above is not needed

    while True:

        logging.info("Worker thread waiting on queue")
        try:
            (basepath, path) = taskq.get(block=False)
        except Empty:
            logging.info("Work queue empty!")
            break

        fpath = os.path.normpath(f"{basepath}/{path}")
        logging.info(f"Worker thread ({current_thread()}) parsing picture: {fpath}")
        add_picture(db.session, basepath, path, dbl)

        doneq.put(fpath)

    logging.info(f"Worker thread ({current_thread()}) exiting")


def scanner(basepath, nthread=1):
    task_queue = Queue()
    done_queue = Queue()
    dbl = Lock()

    # set time scan started
    rb_row = db.session.query(Config).filter(Config.key == "rebuilding").one_or_none()
    rb_row.value = "true"
    rbs_row = db.session.query(Config).filter(Config.key == "rebuild_start").one_or_none()
    rbs_row.value = str(datetime.utcnow().timestamp())
    rbe_row = db.session.query(Config).filter(Config.key == "rebuild_end").one_or_none()
    rbe_row.value = None
    db.session.commit()

    # Scan given directory adding all jpg files to task queue, worker thread will 
    #   get from queue and process them, adding them to the done queue when finished.
    pics = fs.open_fs(basepath)
    count = 0
    for path in pics.walk.files(filter=['*.[Jj][Pp][Gg]']):
        if basename(path)[0] == '.':
            logging.info("skipping {}".format(basename(path)))
            continue

        else:
            task_queue.put((basepath, path))
            count += 1

            dbl.acquire()
            count_row = db.session.query(Config).filter(Config.key == "count").one_or_none()
            count_row.value = str(count)
            db.session.commit()
            dbl.release()

        logging.info(f"Count: {count}")

    # Start worker thread(s)
    for i in range(nthread):
        Thread(target=mp_worker, args=(task_queue,done_queue,dbl)).start()

    # Wait for all pictures to be processed
    done = 0
    for i in range(count):
        fpath = done_queue.get()
        done += 1
        logging.info(f"Done: ({done}/{count}) {fpath}")

        # Update db w/ status as we go
        dbl.acquire()
        done_row = db.session.query(Config).filter(Config.key == "done").one_or_none()
        done_row.value = str(done)
        db.session.commit()
        dbl.release()

    rb_row.value = None
    rbe_row.value = str(datetime.utcnow().timestamp())
    db.session.commit()



def add_all_pictures(basepath):
    # Launch scanner thread, wait for it to finish?
    #p = Process(target=scanner, args=(basepath,))
    wp_row = db.session.query(Config).filter(Config.key == "worker_processes").one_or_none()
    args = (basepath,)
    if wp_row and wp_row.value.isnumeric():
        args=(basepath,int(wp_row.value))

    p = Thread(target=scanner, args=args)
    delete_pictures()
    p.start()
    logging.info(f"Scanner started")

    #p.join()
    #logging.info(f"Scanner finished")
