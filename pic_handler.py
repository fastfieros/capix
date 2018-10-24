import http.server
import sqlite3
from config import DB_PATH, PIC_PATH
from datetime import datetime
from math import ceil
from os.path import basename, dirname, getmtime, realpath
from threading import Thread, Semaphore
from urllib.parse import urlparse, parse_qs
from wand.color import Color
from wand.drawing import Drawing
from wand.image import Image
from collections import deque

from pics import rebuild_thread

SCRIPT_PATH = dirname(realpath(__file__))
HISTORY = None

class MyHandler(http.server.SimpleHTTPRequestHandler):
    rebuilding = Semaphore()
    rbthread = None

    def rebuild_history_deque(self):
        global HISTORY
        con = sqlite3.connect(DB_PATH)
        c = con.cursor()
        c.execute('SELECT client FROM config')
        rows = c.fetchall()
        HISTORY = {}
        for row in rows:
            HISTORY[row[0]] = deque(maxlen=10)

        c.close()
        con.close()

    @staticmethod
    def get_tagq(tags):

        tagq = ""
        tagp = []

        if "," in tags:
            tagp = tags.split(",")
            tagq = 'WHERE '
            tagq += 'tags.tag IN ({}) '.format(",".join("?" * len(tagp)))

        elif tags == "*":
            tagq = ""
            tagp = []

        elif tags != "":
            tagp = [tags]
            tagq = 'WHERE tags.tag = ? '

        # print (tagq, tagp)
        return tagq, tagp

    @staticmethod
    def get_starq(tagq, stars):

        starq = ""
        if tagq == "":
            starq = "WHERE "
        else:
            starq = "AND "

        if stars[0:2] == "<=":
            starq += 'stars <= ? '
            starp = [stars[2:]]
        elif stars[0:2] == ">=":
            starq += 'stars >= ? '
            starp = [stars[2:]]
        elif stars[0] == ">":
            starq += 'stars > ? '
            starp = [stars[1:]]
        elif stars[0] == "<":
            starq += 'stars < ? '
            starp = [stars[1:]]

        elif "," in stars:
            starp = stars.split(",")
            starq += 'stars IN ({}) '.format(",".join("?" * len(starp)))
        elif stars != "":
            starp = stars
            starq += 'stars = ? '

        # print (starq, starp)
        return starq, starp

    def get_minviews(self, cur, tags, stars):
        (tagq, tagp) = self.get_tagq(tags)
        (starq, starp) = self.get_starq(tagq, stars)

        query = 'SELECT min(views) FROM pics ' + \
                'JOIN xtags ON pics.rowid = xtags.picid ' + \
                'JOIN tags ON xtags.tagid = tags.rowid ' + \
                tagq + \
                starq
        params = []
        params.extend(tagp)
        params.extend(starp)

        # print (query)
        # print (params)

        cur.execute(query, params)
        row = cur.fetchone()
        if row:
            return row[0]
        else:
            return None

    def get_row(self, cur, tags, stars, minviews):
        (tagq, tagp) = self.get_tagq(tags)
        (starq, starp) = self.get_starq(tagq, stars)

        query = 'SELECT rowid,path,views,title,description FROM pics ' + \
                'WHERE rowid = (SELECT pics.rowid FROM pics ' + \
                'JOIN xtags ON pics.rowid = xtags.picid ' + \
                'JOIN tags ON xtags.tagid = tags.rowid ' + \
                tagq + \
                starq + \
                'AND views = ? ' + \
                'ORDER BY RANDOM() LIMIT 1) '

        params = []
        params.extend(tagp)
        params.extend(starp)
        params.extend([minviews])

        # print(query)
        # print(params)
        cur.execute(query, params)

        return cur.fetchone()

    def get_row_true_random(self, cur, tags, stars):
        (tagq, tagp) = self.get_tagq(tags)
        (starq, starp) = self.get_starq(tagq, stars)

        query = 'SELECT rowid,path,views,title,description FROM pics ' + \
                'WHERE rowid = (SELECT pics.rowid FROM pics ' + \
                'JOIN xtags ON pics.rowid = xtags.picid ' + \
                'JOIN tags ON xtags.tagid = tags.rowid ' + \
                tagq + \
                starq + \
                'ORDER BY RANDOM() LIMIT 1) '

        params = []
        params.extend(tagp)
        params.extend(starp)

        # print(query)
        # print(params)
        cur.execute(query, params)

        return cur.fetchone()

    @staticmethod
    def do_update(params):
        con = sqlite3.connect(DB_PATH)
        c = con.cursor()

        if "name" not in params or \
                "tag_filter" not in params or \
                "rating" not in params:
            print("Error missing value.")
            return

        if "file_title" in params:
            params['file_title'] = '1'
        else:
            params['file_title'] = '0'

        print ("updating {}".format(params['name'][0]))
        c.execute(
            'UPDATE config SET file_title=:file_title, tag_filter=:tag_filter, rating=:rating, datesize=:datesize, titlesize=:titlesize, font=:font, fill_opacity=:fill_opacity, fill_color=:fill_color, text_under_color=:text_under_color, stroke_opacity=:stroke_opacity, stroke_color=:stroke_color, stroke_width=:stroke_width WHERE client=:name',
            {"file_title": params['file_title'][0],
             "tag_filter": params['tag_filter'][0],
             "rating": params['rating'][0],
             "datesize": params['datesize'][0],
             "titlesize": params['titlesize'][0],
             "name": params['name'][0],
             "font": params['font'][0],
             "fill_opacity": params['fill_opacity'][0],
             "fill_color": params['fill_color'][0],
             "text_under_color": params['text_under_color'][0],
             "stroke_opacity": params['stroke_opacity'][0],
             "stroke_color": params['stroke_color'][0],
             "stroke_width": params['stroke_width'][0]
             })
        con.commit()

        c.close()
        con.close()

    @staticmethod
    def do_delete(params):
        name = params['name'][0]
        # print ("deleting {}".format(name))
        con = sqlite3.connect(DB_PATH)
        c = con.cursor()
        c.execute('DELETE FROM config WHERE client=:name', {"name": name})
        con.commit()
        c.close()
        con.close()

    def get_font_select(self, active=None):
        fonts = ["Montserrat-Black.ttf"
            , "Montserrat-BlackItalic.ttf"
            , "Montserrat-Bold.ttf"
            , "Montserrat-BoldItalic.ttf"
            , "Montserrat-ExtraBold.ttf"
            , "Montserrat-ExtraBoldItalic.ttf"
            , "Montserrat-ExtraLight.ttf"
            , "Montserrat-ExtraLightItalic.ttf"
            , "Montserrat-Italic.ttf"
            , "Montserrat-Light.ttf"
            , "Montserrat-LightItalic.ttf"
            , "Montserrat-Medium.ttf"
            , "Montserrat-MediumItalic.ttf"
            , "Montserrat-Regular.ttf"
            , "Montserrat-SemiBold.ttf"
            , "Montserrat-SemiBoldItalic.ttf"
            , "Montserrat-Thin.ttf"
            , "Montserrat-ThinItalic.ttf"
            , "OFL.txt"
            , "PoiretOne-Regular.ttf"
            , "Raleway-Black.ttf"
            , "Raleway-BlackItalic.ttf"
            , "Raleway-Bold.ttf"
            , "Raleway-BoldItalic.ttf"
            , "Raleway-ExtraBold.ttf"
            , "Raleway-ExtraBoldItalic.ttf"
            , "Raleway-ExtraLight.ttf"
            , "Raleway-ExtraLightItalic.ttf"
            , "Raleway-Italic.ttf"
            , "Raleway-Light.ttf"
            , "Raleway-LightItalic.ttf"
            , "Raleway-Medium.ttf"
            , "Raleway-MediumItalic.ttf"
            , "Raleway-Regular.ttf"
            , "Raleway-SemiBold.ttf"
            , "Raleway-SemiBoldItalic.ttf"
            , "Raleway-Thin.ttf"
            , "Raleway-ThinItalic.ttf"]

        select = "<select name='font'>\n"
        for f in fonts:
            selected = (active == f and " selected" or "")
            select += "<option value={0}{1}>{0}</option>\n".format(f, selected)

        select += "</select>\n"

        return select

    def do_config(self, params):
        self.send_response(200, 'OK')
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        # print("Params: {}",params)
        if "add" in params:
            self.do_add(params)
        elif "update" in params:
            self.do_update(params)
        elif "delete" in params:
            self.do_delete(params)

        confpage = ""

        con = sqlite3.connect(DB_PATH)
        c = con.cursor()
        c.execute(
            'SELECT client, file_title, tag_filter, rating, datesize, titlesize, font, fill_opacity, fill_color, text_under_color, stroke_opacity, stroke_color, stroke_width FROM config')
        rows = c.fetchall()

        for client in rows:

            confpage += "<div style='border:2px solid #888;padding:5px;margin:5px;width:400px;'>\n"
            confpage += "<form method='get' action='/config'>" + \
                        "<h3>{}</h3>".format(client[0]) + \
                        "<input type='hidden' name='update' value='1'\>" + \
                        "<input type='hidden' name='name' value='{}'\>".format(client[0]) + \
                        "Use filename when title is empty: <input type='checkbox' name='file_title' {}/><br>".format(
                            client[1] == 1 and "checked" or "") + \
                        "Tags (* or csv): <input name='tag_filter' value='{}'/><br>".format(client[2]) + \
                        "Stars (<, <=, >, >=, or csv): <input name='rating' value='{}'/><br>".format(client[3]) + \
                        "Date font size: <input name='datesize' value='{}'/><br>".format(client[4]) + \
                        "Title font size: <input name='titlesize' value='{}'/><br>".format(client[5]) + \
                        "Font: {}<br>".format(self.get_font_select(client[6])) + \
                        "Font fill opacity (0-100): <input name='fill_opacity' value='{}'/><br>".format(client[7]) + \
                        "Font fill color: <input name='fill_color' value='{}'/><br>".format(client[8]) + \
                        "Font Background color: <input name='text_under_color' value='{}'/><br>".format(client[9]) + \
                        "Font stroke opacity (0-100): <input name='stroke_opacity' value='{}'/><br>".format(client[10]) + \
                        "Font stroke color: <input name='stroke_color' value='{}'/><br>".format(client[11]) + \
                        "Font stroke width: <input name='stroke_width' value='{}'/><br>".format(client[12]) + \
                        "<input type='submit' value='Update'/></form>\n"

            if client[0] != "default":
                confpage += "<form method='get' action='/config'>" + \
                            "<input type='hidden' name='name' value='{}'/>".format(client[0]) + \
                            "<input type='hidden' name='delete' value='1'\>" + \
                            "<input type='submit' value='Delete'/></form>\n"

            confpage += "<a href='/?name={}'>Preview</a>\n".format(client[0])
            confpage += "<a href='/history?client={}'>Recently Shown</a>\n".format(client[0])
            confpage += "</div>\n"

        confpage += "<hr><div><form method='get' action='/config'>" + \
                    "<input name='name' placeholder='new client name'/><input type='hidden' name='add' value='1'\>" + \
                    "<input type='submit' value='Add New Client'/></form></div>"

        confpage += "<p><a href='/rebuild_db?start=1'>Start database rebuild</a></p><p><a href='/rebuild_db'>View database rebuild status</a></p>"
        self.wfile.write(confpage.encode('UTF-8'))

        c.close()
        con.close()
        return

    def do_auto(self):
        self.send_response(200, 'OK')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        autopage = "<html><head><meta http-equiv='refresh' content='3600'>" + \
                   "<style>html,body{margin:0;height:100%;} .wrap,img{display:block;width:100%;height:100%;object-fit:cover;}</style>" + \
                   "</head>" + \
                   "<div class=wrap><img src='/pic?{}' /></div>".format(urlparse(self.path).query) + \
                   "</html>"
        self.wfile.write(autopage.encode('UTF-8'))

        return

    def do_rebuild_db(self, params):

        msg = ""

        if self.rebuilding.acquire(False):
            if "start" in params:
                msg = "Starting rebuild.."
                self.rbthread = Thread(target=rebuild_thread, args=(self.rebuilding,))
                self.rbthread.start()

            else:  # Just getting status
                msg = "Rebuild complete."
                self.rebuilding.release()

        else:
            msg = "Already rebuilding.."

        self.send_response(200, 'OK')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        page = "<html><h1>{}</h1><a href='/rebuild_db'>update status</a></html>".format(msg)
        self.wfile.write(page.encode('UTF-8'))

        return

    @staticmethod
    def draw_text(jpgimg, dt, title, datesize, titlesize, font,
                  fill_opacity, fill_color, text_under_color, stroke_opacity,
                  stroke_color, stroke_width, x, y):

        left = 0
        right = x #jpgimg.width
        top = 0
        bottom = y #jpgimg.height

        # Enable alpha channel
        jpgimg.alpha_channel = True

        text = Image(width=right, height=bottom)
        text.alpha_channel = True

        # Open draw api to write text onto canvas
        with Drawing() as draw:

            draw.font = SCRIPT_PATH + "\\font\\" +  font
            draw.fill_color = Color(fill_color)
            draw.fill_opacity = float(fill_opacity)/100.0
            #draw.fill_width = fill_width
            draw.stroke_color = Color(stroke_color)
            draw.stroke_opacity = float(stroke_opacity)/100.0
            draw.stroke_width = stroke_width
            if text_under_color and text_under_color.lower() is not 'None':
                draw.text_under_color = Color(text_under_color) #'#00000030'

            right_buf = 0
            # Add date taken
            if dt:
                draw.font_size = datesize
                dtp = datetime.strptime(dt, "%Y-%m-%d")
                dts = dtp.strftime("%b '%y")
                print(dts)
                metrics = draw.get_font_metrics(text, dts, False)
                right_buf = int(metrics.text_width) + 10
                draw.text(right - right_buf, bottom - 10, dts)
                right_buf += 10

            # Add title if available
            if title:
                draw.font_size = titlesize
                metrics = draw.get_font_metrics(text, title, False)
                skip = metrics.text_height
                cur_line = int(bottom - 10)
                max_width = jpgimg.width - right_buf

                # Perform wrapping if needed
                if metrics.text_width > max_width:
                    q = ceil(metrics.text_width / max_width)
                    charsperline = int((2.0/3.0) * (len(title) / q))
                    cur_char = len(title)
                    while True:
                        next_char = cur_char - charsperline
                        if next_char < 0:
                            next_char = 0
                        else:
                            # Find next backwards space
                            while title[next_char] != ' ' and next_char > 0:
                                next_char -= 1

                        # print("{}->{}: {}".format(next_char, cur_char, label[next_char:cur_char]))
                        draw.text(left + 10, cur_line, title[next_char:cur_char])
                        cur_char = next_char
                        cur_line -= int(skip)

                        if 0 == next_char:
                            break

                else:
                    draw.text(left + 10, cur_line, title)
                    cur_line -= int(skip)

            # Render text onto canvas image
            draw(text)
            jpgimg.composite(image=text, left=left, top=top)

    def do_GET(self):
        global HISTORY

        if HISTORY is None:
            self.rebuild_history_deque()

        # We don't need no favicon
        if self.path.startswith("/favicon"):
            self.send_response(404, 'Not Found')
            self.end_headers()
            self.wfile.write(b"<html><h1>Error: No favicon.</h1></html>")
            return

        # Parse query from feh (or browswer).
        params = parse_qs(urlparse(self.path).query)

        if self.path.startswith("/config"):
            self.do_config(params)
            return

        if self.path.startswith("/auto"):
            return self.do_auto()

        if self.path.startswith("/rebuild_db"):
            return self.do_rebuild_db(params)

        if self.path.startswith("/history"):
            return self.do_history(params)

        if self.path.startswith("/thumbnail"):
            return self.do_thumbnail(params)

        # Connect to pictures database
        con = sqlite3.connect(DB_PATH)
        c = con.cursor()

        # Get the settings for this client
        client = 'default'
        if 'name' in params:
            client = params['name'][0]

        c.execute(
            'SELECT file_title, tag_filter, rating, datesize, titlesize, font, fill_opacity, fill_color, text_under_color, stroke_opacity, stroke_color, stroke_width FROM config WHERE client=:client',
            {"client": client})
        row = c.fetchone()
        if not row:
            self.send_response(404, 'Not Found')
            self.end_headers()
            self.wfile.write(b"<html><h1>Error: No matching client.</h1></html>")
            return

        file_title = row[0]
        tagfilter = row[1]
        stars = row[2]
        datesize = row[3]
        titlesize = row[4]
        font = row[5]
        fill_opacity = row[6]
        fill_color = row[7]
        text_under_color = row[8]
        stroke_opacity = row[9]
        stroke_color = row[10]
        stroke_width = row[11]
        print("{}/{}/{}/{}/{}/{}/{}/{}/{}/{}/{}/{}".format(file_title, tagfilter, stars, datesize, titlesize, font,
                                                     fill_opacity, fill_color, text_under_color, stroke_opacity, stroke_color,
                                                     stroke_width))

        # Get the list of matching pictures, just to find the minimum
        # view count. This query will return only a single value: the
        # min view count.
        # minviews = self.get_minviews(c, tagfilter, stars)
        # if minviews is None:
        #    self.send_response(404, 'Not Found')
        #    self.end_headers()
        #    self.wfile.write(b"<html><h1>Error: No matching pics.</h1></html>")
        #    return
        #
        # Get the same list filtered by viewcount so that we only choose
        # from pictures with the minimum views. (this keeps all pictures
        # in fair rotation). Then sort by random and get the first one.
        # row = self.get_row(c, tagfilter, stars, minviews)
        row = self.get_row_true_random(c, tagfilter, stars)
        if not row:
            self.send_response(404, 'Not Found')
            self.end_headers()
            self.wfile.write(b"<html><h1>Error.</h1></html>")
            return

        else:
            rowid = row[0]
            path = row[1]
            views = int(row[2]) + 1
            title = row[3]
            desc = row[4]
            print ("{}:{}, {} views ({})".format(rowid, path, views, title))

            HISTORY[client].appendleft(path)

            # Now that we have chosen a picture, update its view count in db.
            c.execute('UPDATE pics SET views=:views WHERE rowid=:rowid', {"views": views, "rowid": rowid})
            con.commit()

            (x, y) = (1920, 1080)  # default 1080p
            if 'r' in params:
                (x, y) = params['r'][0].lower().split('x')
                (x, y) = (int(x), int(y))

            # Create base canvas (blank image of correct size)
            img = Image(width=x, height=y, background=Color('black'))
            img.alpha_channel = True

            # Add label (Default label is filename, title if available)
            label = ""
            if title and title != "":
                label = title
            elif file_title == 1:
                label = basename(path)
                if label.startswith("/"):
                    label = label[1:]  # Remove leading /

            # Open canvas containing jpg pixels, for resizing.
            with Image(filename=PIC_PATH + path) as jpgimg:

                dt = None
                if "exif:DateTimeOriginal" in jpgimg.metadata:
                    dt = jpgimg.metadata['exif:DateTimeOriginal'].split(" ")[0].replace(":", "-")

                if "exif:Orientation" in jpgimg.metadata:
                    o = jpgimg.metadata['exif:Orientation']
                    print("ORIENTATION:", o)
                    if o == '3':
                        jpgimg.rotate(180)
                    elif o == '6':
                        jpgimg.rotate(90)
                    elif o == '8':
                        jpgimg.rotate(270)

                # Fit within box, maintain AR (aka 'fit'). add '>' to the end to avoid enlarging small pictures.
                jpgimg.transform(resize="{:d}x{:d}".format(x, y))

                # Place jpgimage in center of canvas
                img.composite(image=jpgimg, left=int((x - jpgimg.width) / 2), top=int((y - jpgimg.height) / 2))

                # Draw text over jpgimg
                self.draw_text(img, dt, label, datesize, titlesize, font, fill_opacity, fill_color, text_under_color,
                               stroke_opacity, stroke_color, stroke_width, x, y)

                # Send HTTP response to feh (or browser)
                self.send_response(200, 'OK')
                self.send_header('Content-type', 'image/jpeg')
                self.end_headers()

                # Send final image to feh (or browser)
                self.wfile.write(img.make_blob('jpeg'))

        # cleanup
        c.close()
        con.close()


    def do_add(self, params):
        name = params['name'][0]
        print ("adding {}".format(name))
        con = sqlite3.connect(DB_PATH)
        c = con.cursor()
        c.execute(
            'INSERT INTO config (client, file_title, tag_filter, rating, datesize, titlesize) VALUES (:name, 1, "*", ">0", 60, 40)',
            {"name": name})
        con.commit()
        c.close()
        con.close()
        self.rebuild_history_deque()

    def do_history(self, params):
        global HISTORY

        mydeque = HISTORY[params['client'][0]]
        if len(mydeque) == 0:
            historylist = "No history"
        else:
            con = sqlite3.connect(DB_PATH)
            c = con.cursor()

            historylist = "<div>\n"

            query = 'SELECT path, title, GROUP_CONCAT(tags.tag) FROM pics ' + \
                    'JOIN xtags ON pics.rowid = xtags.picid ' + \
                    'JOIN tags ON xtags.tagid = tags.rowid ' + \
                    'WHERE path in ({})'.format(','.join('?' * len(mydeque))) + \
                    'GROUP BY path '

            c.execute(query, tuple(mydeque))
            rows = c.fetchall()
            c.close()
            con.close()

            i = 0
            for item in mydeque:
                if i > 5:
                    break
                for row in rows:
                    if row[0] == item:
                        historylist += "<div style='float: left; margin: 5px; padding:0; border:solid 2px #888; width:200px;'><img src='/thumbnail?path={}' /><div style='padding: 5px;'><b>{}</b><br><i>{}</i><br><small>{}</small></div></div>\n".\
                        format(row[0], row[1], row[2], row[0])
                        i += 1
                        break

            historylist += "</div>\n"

        self.send_response(200, 'OK')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        page = "<html>{}</html>".format(historylist)
        self.wfile.write(page.encode('UTF-8'))

    def do_thumbnail(self, params):
        #TODO: Use rowid not path
        with Image(filename=PIC_PATH + params['path'][0]) as jpgimg:

            if "exif:Orientation" in jpgimg.metadata:
                o = jpgimg.metadata['exif:Orientation']
                print("ORIENTATION:", o)
                if o == '3':
                    jpgimg.rotate(180)
                elif o == '6':
                    jpgimg.rotate(90)
                elif o == '8':
                    jpgimg.rotate(270)

            # Fit within box, maintain AR (aka 'fit'). add '>' to the end to avoid enlarging small pictures.
            jpgimg.transform(resize="{:d}x{:d}".format(200, 300))

            # Send HTTP response to feh (or browser)
            self.send_response(200, 'OK')
            self.send_header('Content-type', 'image/jpeg')
            self.end_headers()

            # Send final image to feh (or browser)
            self.wfile.write(jpgimg.make_blob('jpeg'))
