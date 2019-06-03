#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import queue
import cherrypy as cp
import sys

from functools import partial
from worker import Worker


class WorkerApp:

    def __init__(self, worker_queue):
        self.worker_queue = worker_queue

    @cp.expose
    @cp.tools.json_in()
    def index(self):
        data = cp.request.json
        self.worker_queue.put(data)


def stop_worker(q):
    q.put(None)


def _get_password():
    path = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(path, '.secret')
    with open(filename, encoding='utf-8') as fp:
        return fp.read().strip()


user = {'cm': _get_password()}
check = cp.lib.auth_basic.checkpassword_dict(user)
config = {
    'global': {
        'server.socket_host': '127.0.0.1',
        'server.socket_port': 12012,
        'server.thread_pool': 8,
        'server.socket_timeout': 60,
    },
    '/': {
        'tools.auth_basic.on': True,
        'tools.auth_basic.realm': 'msds_worker',
        'tools.auth_basic.checkpassword': check,
    },
}


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'production':
        config['global']['environment'] = 'production'
    q = queue.Queue()
    w = Worker(q)
    w.start()
    cp.engine.subscribe('stop', partial(stop_worker, q))
    cp.quickstart(WorkerApp(q), '/', config)
