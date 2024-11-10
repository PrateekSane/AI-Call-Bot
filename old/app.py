# app.py
from flask import Flask
from flask_sockets import Sockets

app = Flask(__name__)
sockets = Sockets(app)

# Import your routes to register them with the app
import routes2
import ws_handler2

if __name__ == '__main__':
    from gevent import monkey
    monkey.patch_all()
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler

    server = pywsgi.WSGIServer(('', 5100), app, handler_class=WebSocketHandler)
    server.serve_forever()
