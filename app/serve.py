#!/usr/bin/env python3

import collections
import logging
import os
import pprint
import sys

import momoko
import psycopg2
import tornado.ioloop
import tornado.platform.asyncio
import tornado.web
import tornado.websocket

log = logging.getLogger('wikipedia_live.main')


class Listeners:

    def __init__(self):
        self.listeners = collections.defaultdict(set)

    def add(self, table_name, conn):
        """Insert this connection into the list that will be notified on new messages."""
        self.listeners[table_name].add(conn)

    def broadcast(self, table_name, payload):
        """Write the message to all listeners. May remove closed connections."""
        if table_name not in self.listeners:
            return

        closed_listeners = set()
        for listener in self.listeners[table_name]:
            try:
                listener.write_message(payload)
            except tornado.websocket.WebSocketClosedError:
                closed_listeners.add(listener)

        for closed_listener in closed_listeners:
            self.listeners.remove(closed_listener)

    def remove(self, table_name, conn):
        """Remove this connection from the list that will be notified on new messages."""
        try:
            self.listeners[table_name].remove(conn)
        except KeyError:
            pass


class BaseWebSocketHandler(tornado.websocket.WebSocketHandler):

    @property
    def listeners(self):
        return self.application.listeners


class BaseHandler(tornado.web.RequestHandler):

    @property
    def listeners(self):
        return self.application.listeners

    @property
    def mzql(self):
        return self.application.mzql


class IndexHandler(BaseHandler):

    async def get(self):

        counts_cursor = await self.mzql.execute('SELECT * FROM counter')
        edit_count = counts_cursor.fetchone()[0]

        editors_cursor = await self.mzql.execute('SELECT * FROM top10 ORDER BY count DESC')
        editors = [(name, count) for (name, count) in editors_cursor]
        self.render('index.html', edit_count=edit_count, editors=editors)


class StreamHandler(BaseWebSocketHandler):

    def open(self, table):
        self.table_name = table
        self.listeners.add(self.table_name, self)

    def on_close(self):
        self.listeners.remove(self.table_name, self)


class UpdateHandler(BaseHandler):

    async def post(self, table_name):
        delta = tornado.escape.json_decode(self.request.body)
        payload = {'table': table_name, 'delta': delta}
        self.listeners.broadcast(table_name, payload)


def configure_logging():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def run():
    configure_logging()

    handlers = [
        tornado.web.url(r'/', IndexHandler, name='index'),
        tornado.web.url(r'/api/v1/stream/(.*)', StreamHandler, name='api/stream'),
        tornado.web.url(r'/api/v1/update/(.*)', UpdateHandler, name='api/update'),
    ]

    base_dir = os.path.dirname(__file__)
    static_path = os.path.join(base_dir, 'static')
    template_path = os.path.join(base_dir, 'templates')

    app = tornado.web.Application(handlers,
                                  static_path=static_path,
                                  template_path=template_path,
                                  debug=True)

    app.listeners = Listeners()

    dsn = 'host=localhost port=6875 dbname=materialize'
    app.mzql = momoko.Pool(dsn=dsn)

    # Connect Momoko before starting Tornado's event loop
    # This let's Momoko create an initial connection to the database
    future = app.mzql.connect()
    ioloop = tornado.ioloop.IOLoop.current()
    ioloop.add_future(future, lambda f: ioloop.stop())
    ioloop.start()

    port = 8875
    log.info('Port %d ready to rumble!', port)
    app.listen(port)
    ioloop.start()


if __name__ == '__main__':
    run()
