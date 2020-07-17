#!/usr/bin/env python3

import logging
import os
import pprint
import sys

import momoko
import psycopg2
import tornado.ioloop
import tornado.platform.asyncio
import tornado.web

log = logging.getLogger('wikipedia_live.main')


class Listeners:

    def write(self, table_name, json_payload):
        print('Received delta for table {}: {}'.format(table_name, json_payload))


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


class UpdateHandler(BaseHandler):

    async def post(self, table_name):
        delta = tornado.escape.json_decode(self.request.body)
        self.listeners.write(table_name, delta)


def configure_logging():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def run():
    configure_logging()

    handlers = [
        tornado.web.url(r'/', IndexHandler, name='index'),
        tornado.web.url(r'/api/v1/(.*)', UpdateHandler, name='index'),
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
