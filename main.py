import http.server
import socketserver
import os
from config import DB_PATH, PIC_PATH

from pic_handler import MyHandler
from pics import rebuild_db

if __name__ == "__main__":

    rebuild_db(DB_PATH, PIC_PATH)

    with socketserver.TCPServer(("", 8000), MyHandler) as httpd:
        print("Serving on port 8000")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("exiting")
