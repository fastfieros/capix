import fs
import sqlite3
from config import DB_PATH, PIC_PATH
from datetime import datetime
from os.path import basename, dirname, getmtime, realpath
from threading import Thread, Semaphore

from py_avm import AVM, exceptions

SCRIPT_PATH = dirname(realpath(__file__))

def add_tag(cur, tag, rowid):
    tagid = None

    # Only add the tag if it's not already there.
    cur.execute("SELECT rowid FROM tags WHERE tag = :tag", {"tag": tag})
    row = cur.fetchone()

    if not row:
        cur.execute("INSERT INTO tags VALUES (:tag)", {"tag": tag})
        tagid = cur.lastrowid
    else:
        tagid = row[0]

    cur.execute("INSERT INTO xtags VALUES (:picid, :tagid)", {"picid": rowid, "tagid": tagid})


def add_tags(cur, tags, rowid):
    for tag in tags:
        add_tag(cur, tag.lower(), rowid)


def add_file(cur, basepath, filepath):
    # use (customized) astronomy metadata library because it's the only
    # pure python metadata parser that can handle embedded xmp.
    stars = 0
    tags = None
    title = ""
    desc = ""

    try:
        avm = AVM.from_image(basepath + filepath)

        if avm.Rating and avm.Rating > 0:
            stars = avm.Rating

        if avm.Subject.Name and len(avm.Subject.Name):
            tags = avm.Subject.Name

        if avm.Title:
            title = avm.Title

        if avm.Description:
            desc = avm.Description

    except (exceptions.NoXMPPacketFound, ValueError):
        print ("{} has no XMP data.".format(filepath))

    mtime = getmtime(basepath + filepath)

    cur.execute('INSERT INTO pics VALUES (:path,0,0,:stars,:title,:description,:mtime)',
                {"path": filepath, "stars": stars, "title": title, "description": desc, "mtime": mtime})

    # Tags are kept in 2 additional tables. One is a list of all tag names, the
    # other is a many-to-many map of picture id to tag id. 
    if tags:
        add_tags(cur, tags, cur.lastrowid)
    else:
        add_tags(cur, ['no_tag'], cur.lastrowid)

    # print ("Added new pic {}".format(filepath))


def build_db(cur, basepath):
    pics = fs.open_fs(basepath)

    count = 0
    for path in pics.walk.files(filter=['*.[Jj][Pp][Gg]']):
        if basename(path)[0] == '.':
            # print ("skipping {}".format(basename(path)))
            continue

        # print ("Checking {}".format(basename(path)))
        cur.execute("SELECT rowid,mtime,path FROM pics WHERE path LIKE :filename", {"filename": "%" + basename(path)})
        row = cur.fetchone()
        if row:
            # This pic is in the db, and it still exists. Check if filemtime is
            # newer than what we have in the db
            db_mtime = row[1]
            file_mtime = getmtime(basepath + path)
            if file_mtime > db_mtime:
                # File has been modified since adding to db, so we will delete
                # the original and add the file again (a new entry). As a side
                # effect, view count will be reset to 0, so it will be shown
                # again sooner
                cur.execute('DELETE FROM pics WHERE rowid=:rowid', {"rowid": row[0]})
                print ("File: {} modified".format(row[2]))
                add_file(cur, basepath, path)

            else:
                # Mark it clean.
                cur.execute('UPDATE pics SET dirty=0 WHERE rowid=:id', {"id": row[0]})
                # print ("Pic {} now clean".format(row[0]))

        else:
            # This pic is new (was not in the cb). Add it  to the db.
            add_file(cur, basepath, path)

        count += 1
        print(count)

    # Remove all dirty rows (pics that were in the db but no longer in the fs).
    cur.execute(
        'DELETE FROM xtags WHERE rowid IN (SELECT xtags.rowid FROM xtags JOIN pics ON pics.rowid = picid WHERE pics.dirty=1)')
    cur.execute('DELETE FROM pics WHERE dirty=1')
    print ("{} pics in database.".format(count))


def rebuild_db(db_path, basepath):
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Check if table exists, or create it:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pics'")
    row = cur.fetchone()
    if row:
        # Table exists, mark all rows dirty.
        cur.execute('UPDATE pics SET dirty=1')
        print("table exists, updating..")

    else:
        # Table doesn;t exists, create empty table.
        cur.execute(
            'CREATE TABLE pics (path text unique, views int, dirty boolean, stars float, title text, description text, mtime int)')
        cur.execute('CREATE INDEX idx_stars ON pics(stars)')

        cur.execute('CREATE TABLE tags (tag text unique)')

        cur.execute('CREATE TABLE xtags (picid int, tagid int)')
        cur.execute('CREATE INDEX idx_tags ON xtags(tagid,picid)')

        cur.execute(
            'CREATE TABLE config (client text unique, file_title int, tag_filter text, rating text, datesize int, titlesize int, font text, fill_opacity int, fill_color text, stroke_opacity int, stroke_color text)')
        cmd = 'INSERT INTO config VALUES ("default", 1, "*", ">0", 60, 40, "' + SCRIPT_PATH + "\\font\\PoiretOne-Regular.ttf" + '", 90, "white", 20, "black")'
        print(cmd)
        cur.execute(cmd)
        con.commit()

        print("no table exists, creating..")

    build_db(cur, basepath)
    con.commit()
    cur.close()
    con.close()


def rebuild_thread(sem):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('UPDATE pics SET dirty=1')
    build_db(cur, PIC_PATH)
    con.commit()
    cur.close()
    con.close()
    sem.release()
