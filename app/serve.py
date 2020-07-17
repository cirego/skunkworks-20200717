#!/usr/bin/env python3

import logging
import os
import sys

import momoko
import psycopg2
import tornado.ioloop
import tornado.platform.asyncio
import tornado.web

log = logging.getLogger('wikipedia_live.main')

class BaseHandler(tornado.web.RequestHandler):

    @property
    def mzql(self):
        return self.application.mzql


class IndexHandler(BaseHandler):

    async def get(self):

        counts_cursor = await self.mzql.execute('SELECT * FROM counter')
        edit_count = counts_cursor.fetchone()[0]

        editors_cursor = await self.mzql.execute('SELECT * FROM top10')
        editors = [(name, count) for (name, count) in editors_cursor]
        self.render('index.html', edit_count=edit_count, editors=editors)


def configure_logging():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def run():
    configure_logging()

    handlers = [
        tornado.web.url(r'/', IndexHandler, name='index')
    ]

    base_dir = os.path.dirname(__file__)
    static_path = os.path.join(base_dir, 'static')
    template_path = os.path.join(base_dir, 'templates')

    app = tornado.web.Application(handlers,
                                  static_path=static_path,
                                  template_path=template_path,
                                  debug=True)

    app_id = 'wikipedia_live_dashboard'
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
