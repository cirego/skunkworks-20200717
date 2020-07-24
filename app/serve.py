#!/usr/bin/env python3

import collections
import logging
import os
import pprint
import sys

import momoko
import tornado.ioloop
import tornado.platform.asyncio
import tornado.web
import tornado.websocket

log = logging.getLogger('wikipedia_live.main')

RowUpdate = collections.namedtuple('update', ['columns', 'operation', 'timestamp'])

# We are going to send a never-ending stream of View Updates
# A ViewUpdate contains a set of inserts and deletes bound to a timestamp
# Insert and Delete operations are conflict-free and can be applied in either order

class ViewUpdate:

    def __init__(self, from_timestamp, to_timestamp):
        """A view update transforms a view from the previous to the current view."""
        self.from_timestamp = from_timestamp
        self.to_timestamp = to_timestamp
        self.to_insert = set()
        self.to_delete = set()

    def merge(self, new_view):
        """Incorporate updates from another ViewUpdate into this one."""
        assert self.to_timestamp == new_view.from_timestamp
        self.to_timestamp = new_view.to_timestamp

        # Add rows inserted by the new view
        self.to_insert.update(new_view.to_insert)

        # Drop rows deleted by the new view
        self.to_insert.difference_update(new_view.to_delete)

    def update(self, row, old=False):
        if not old:
            assert row.timestamp == self.to_timestamp

        if row.operation == 'delete':
            self.to_insert.discard(row.columns)
            self.to_delete.add(row.columns)
        else:
            assert row.operation == 'insert'
            assert row.columns not in self.to_delete, "Out of order DELETE"
            self.to_insert.add(row.columns)

        assert self.to_insert.intersection(self.to_delete) == set(), "Conflicting updates!"

    def to_serializable(self):
        msg = {'insert': list(self.to_insert),
                'delete': list(self.to_delete),
                'from_timestamp': self.from_timestamp,
                'to_timestamp': self.to_timestamp}
        pprint.pprint(msg)
        return msg

class TableCache:

    def __init__(self):
        self.listeners = set()

        # A stable view of our table
        self.stable_view = ViewUpdate(0, 0)
        self.pending_view = None

    def add(self, conn):
        """Add a new connection, sending the initial state of the stable view."""
        self.listeners.add(conn)
        conn.write_message(self.stable_view.to_serializable())

    def broadcast(self, msg):
        """Write the message to all listeners. May remove closed connections."""
        closed_listeners = set()
        for listener in self.listeners:
            try:
                listener.write_message(msg)
            except tornado.websocket.WebSocketClosedError:
                closed_listeners.add(listener)

        for closed_listener in closed_listeners:
            self.listeners.remove(closed_listener)

    def handle_update(self, update):
        """Process an incoming message from Materialize."""

        # Initial condition -- there is no Pending View. Create one from our message
        # The initial update is from [0, update.timestamp]
        if not self.pending_view:
            self.pending_view = ViewUpdate(0, update.timestamp)

        # Buffer messages with the same timestamp
        if self.pending_view.to_timestamp == update.timestamp:
            self.pending_view.update(update)
            return

        # Special case for Out of Order messages. Just incorporate them as usual but apply them
        # at the pending timestamp rather than their actual timestamp
        if self.pending_view.to_timestamp > update.timestamp:
            self.pending_view(update, old=True)
            return

        # Caution: Views may not contain fully processed timestamps, as there may still be
        # messages coming at a later timestamp. 
        # TODO: It's possible that pending view includes deletes that are not part of either view
        # We should avoid sending these deletes to our listeners. Given that a delete should
        # always follow the insert, it should be safe to drop a delete iff no matching insert can
        # be found in the union of the stable and pending views.

        # Flush the previously buffered view update
        print('Client state should be:')
        self.stable_view.to_serializable()
        print('Client should apply patch:')
        self.broadcast(self.pending_view.to_serializable())

        # Update stable view to be [0, OLD_PENDING]
        self.stable_view.merge(self.pending_view)

        print('Client should end up with view:')
        self.stable_view.to_serializable()

        # We are now the pending view update from (OLD_PENDING, update.timestamp]
        self.pending_view = ViewUpdate(self.stable_view.to_timestamp, update.timestamp)
        self.pending_view.update(update)

    def clear_view(self):
        """Reset this view and the view of all listeners."""
        self.stable_view = ViewUpdate(0, 0)
        self.pending_view = None
        self.broadcast(self.stable_view.to_serializable())

    def remove_listener(self, conn):
        """Stop sending updates to this connection."""
        if conn in self.listeners:
            self.listeners.remove(conn)

class Listeners:

    def __init__(self):
        self.tables = collections.defaultdict(TableCache)

    def add(self, table_name, conn):
        """Insert this connection into the list that will be notified on new messages."""
        self.tables[table_name].add(conn)

    def clear(self, table_name):
        self.tables[table_name].clear_view()

    def handle_update(self, table_name, update):
        self.tables[table_name].handle_update(update)

    def remove(self, table_name, conn):
        """Remove this connection from the list that will be notified on new messages."""
        self.tables[table_name].remove_listener(conn)

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
        print("Update: {}".format(update))
        self.listeners.handle_update(table_name, update)

    async def delete(self, table_name):
        self.listeners.clear(table_name)


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
