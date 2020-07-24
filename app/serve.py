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

RowUpdate = collections.namedtuple('update', ['columns', 'operation', 'timestamp'])

class Listeners:

    def __init__(self):
        self.listeners = collections.defaultdict(set)
        self.cache = collections.defaultdict(set)

    def add(self, table_name, conn):
        """Insert this connection into the list that will be notified on new messages."""
        self.listeners[table_name].add(conn)
        for update in self.cache[table_name]:
            conn.write_message(update._asdict())

    def broadcast(self, table_name, update):
        """Write the message to all listeners. May remove closed connections."""

        if update.operation == 'insert':
            self.cache[table_name].add(update)
        else:
            assert(update.operation == 'delete')
            try:
                old_row = RowUpdate(update.columns, 'insert', update.timestamp)
                self.cache[table_name].remove(old_row)
            except KeyError:
                # Differential may tell us about updates we've never observed
                pass

        if not self.listeners[table_name]:
            return

        payload = update._asdict()

        closed_listeners = set()
        for listener in self.listeners[table_name]:
            try:
                listener.write_message(payload)
            except tornado.websocket.WebSocketClosedError:
                closed_listeners.add(listener)

        for closed_listener in closed_listeners:
            self.listeners.remove(closed_listener)

    def clear_cache(self, table_name):
        if table_name in self.cache:
            del self.cache[table_name]

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
        self.render('index.html')


class StreamHandler(BaseWebSocketHandler):

    def open(self, table):
        self.table_name = table
        self.listeners.add(self.table_name, self)

    def on_close(self):
        self.listeners.remove(self.table_name, self)


class UpdateHandler(BaseHandler):

    async def post(self, table_name):
        # Would be nice to do RowUpdate(**contents) but we need to convert columns to a tuple :-/
        contents = tornado.escape.json_decode(self.request.body)
        update = RowUpdate(tuple(contents['columns']), contents['operation'], contents['timestamp'])
        self.listeners.broadcast(table_name, update)

    async def delete(self, table_name):
        self.listeners.clear_cache(table_name)


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
