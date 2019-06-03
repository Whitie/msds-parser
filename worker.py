#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import requests
import sys

from subprocess import call
from tempfile import TemporaryDirectory
from threading import Thread

import prepare
import sdbparser
import uba


WORKDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'workdir')
UBA_FILE = os.path.join(WORKDIR, 'uba.json')


class Worker(Thread):

    def __init__(self, queue):
        Thread.__init__(self)
        self.queue = queue

    def run(self):
        if not os.path.isfile(UBA_FILE):
            uba.main(WORKDIR)
        while True:
            item = self.queue.get()
            if item is None:
                break
            self._process_item(**item)

    def _process_item(self, download_url, result_url, **kw):
        token = kw.get('security_token', '')
        tmp = TemporaryDirectory(prefix='msds-', dir=WORKDIR)
        outdir = os.path.join(tmp.name, 'out')
        json_file = os.path.join(outdir, 'all.json')
        result_file = os.path.join(outdir, 'single_chem.json')
        r = requests.get(download_url)
        if r.status_code != 200:
            return
        with open(os.path.join(tmp.name, 'sdb.pdf'), 'wb') as fp:
            fp.write(r.content)
        sdbparser.batch_call(outdir, [tmp.name], True, UBA_FILE)
        if not os.path.isfile(json_file):
            return
        with open(json_file, encoding='utf-8') as fp:
            data = json.load(fp)
        try:
            prepare.prepare_data(data[0], outdir)
        except:
            pass
        if os.path.isfile(result_file):
            with open(result_file, encoding='utf-8') as fp:
                result = json.load(fp)
            result['security_token'] = token
            requests.post(result_url, json=result)

