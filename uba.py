#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import time

import requests

from argparse import ArgumentParser
from csv import DictReader
from tempfile import TemporaryDirectory
from zipfile import ZipFile


DATA_FILE = 'uba.json'
ZIP_FILE = 'uba.zip'
MAX_DATA_AGE = 30
UBA_URL = (
    'http://webrigoletto.uba.de/rigoletto/public/'
    'searchRequest.do?event=zipDownload'
)


def need_download(data_dir='.', max_data_age=MAX_DATA_AGE):
    """
    Determines if the data must be downloaded. Returns true if the datafile
    is not present or outdated.

    :parameters:
        data_dir : str
            The directory to store the datafile in.
        max_data_age : int
            The maximum age of the data in days.

    :rtype: bool
    """
    data_path = os.path.join(data_dir, DATA_FILE)
    _max_age = max_data_age * 86400
    if not os.path.isfile(data_path):
        return True
    else:
        stat = os.stat(data_path)
        age = min(stat.st_atime, stat.st_mtime, stat.st_ctime)
        if age < time.time() - _max_age:
            return True
    return False


def download_and_extract_data(tmp_dir=None):
    """
    Downloads the newest data dump as zip from UBA and extracts all files
    to the given dir or a new temporary dir.

    :parameters:
        tmp_dir : TemporaryDirectory
            The TemporaryDirectory object to store the downloaded and
            extracted data in.

    :returns: The directory object where the files are.
    :rtype: TemporaryDirectory
    """
    if tmp_dir is None:
        tmp_dir = TemporaryDirectory(suffix='-sdb', prefix='tmp-')
    zip_path = os.path.join(tmp_dir.name, ZIP_FILE)
    req = requests.get(UBA_URL)
    req.raise_for_status()
    with open(zip_path, 'wb') as fp:
        fp.write(req.content)
    with ZipFile(zip_path) as zf:
        zf.extractall(tmp_dir.name)
    return tmp_dir


def make_data_file(tmp_dir, data_dir='.', cleanup=True):
    """
    Reads all CSV files and stores the data in various ways in a JSON structure.

    :parameters:
        tmp_dir : TemporaryDirectory
            The temp dir where the CSV files are.
        data_dir : str
            The directory to store the data (JSON) file in.
        cleanup : bool
            Remove the temp dir after operation?

    :returns: Path to the data file.
    :rtype: str
    """
    raw_data = _collect_data(tmp_dir)
    name_cas = {}
    name_en_cas = {}
    name_de_en = {}
    cas_all = {}
    for item in raw_data.values():
        if not item.get('cas', ''):
            continue
        try:
            name_cas[item['name'].lower()] = item['cas']
        except KeyError:
            pass
        try:
            name_en_cas[item['name_en'].lower()] = item['cas']
        except KeyError:
            pass
        try:
            name_de_en[item['name'].lower()] = item['name_en'].lower()
        except KeyError:
            pass
        cas_all[item['cas']] = item.copy()
    data_path = os.path.join(data_dir, DATA_FILE)
    data = dict(name_cas=name_cas, name_en_cas=name_en_cas, cas_all=cas_all,
                name_de_en=name_de_en)
    with open(data_path, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, indent=2, sort_keys=True)
    if cleanup:
        tmp_dir.cleanup()
    return data_path


def main(data_dir='.', tmp_dir=None, max_data_age=MAX_DATA_AGE, cleanup=True):
    if need_download(data_dir, max_data_age):
        tmp = download_and_extract_data(tmp_dir)
        path = make_data_file(tmp, data_dir, cleanup)
    else:
        path = os.path.join(data_dir, DATA_FILE)
    with open(path, encoding='utf-8') as fp:
        data = json.load(fp)
    return data


def _collect_data(tmp_dir):
    data = {}
    num = 0
    with open(os.path.join(tmp_dir.name, 'Export_Cas_Nummern.csv')) as fp:
        try:
            reader = DictReader(fp, delimiter='|')
            for row in reader:
                num = int(row['KENN-NUMMER'])
                if num not in data:
                    data[num] = {}
                data[num]['cas'] = row['CAS_NR']
        except:
            if num:
                if num not in data:
                    data[num] = {}
                data[num]['cas'] = ''
    with open(os.path.join(tmp_dir.name, 'Export_EG_Nummern.csv')) as fp:
        try:
            reader = DictReader(fp, delimiter='|')
            for row in reader:
                num = int(row['KENN-NUMMER'])
                if num not in data:
                    data[num] = {}
                data[num]['einecs'] = row['EG_NR']
        except:
            if num:
                if num not in data:
                    data[num] = {}
                data[num]['einecs'] = ''
    with open(os.path.join(tmp_dir.name, 'Export_Stofftabelle.csv')) as fp:
        try:
            reader = DictReader(fp, delimiter='|')
            for row in reader:
                num = int(row['KENN-NUMMER'])
                if num not in data:
                    data[num] = {}
                data[num]['name'] = row['EINSTUFUNGSBEZEICHNUNG']
                data[num]['name_en'] = ''
                if row['WGK'].strip() == 'nwg':
                    data[num]['wgk'] = 0
                else:
                    try:
                        data[num]['wgk'] = int(row['WGK'])
                    except ValueError:
                        data[num]['wgk'] = None
        except:
            if num:
                if num not in data:
                    data[num] = {}
                data[num]['name'] = ''
                data[num]['wgk'] = None
    with open(os.path.join(tmp_dir.name, 'Export_Synonyme.csv')) as fp:
        try:
            reader = DictReader(fp, delimiter='|')
            for row in reader:
                try:
                    num = int(row['KENN-NUMMER'])
                except ValueError:
                    continue
                if num not in data:
                    data[num] = {}
                try:
                    data[num]['synonyms'].append(row['NAME'])
                except KeyError:
                    data[num]['synonyms'] = [row['NAME']]
        except:
            if num:
                if num not in data:
                    data[num] = {}
                data[num]['synonyms'] = []
    return data


def _parse_commandline():
    p = ArgumentParser(description='Download and save chem data from the UBA.')
    p.add_argument('--data-dir', '-d', default='.',
                   help='Directory to save the extracted data in '
                   '(default: %(default)s)')
    p.add_argument('--max-age', '-m', type=int, default=MAX_DATA_AGE,
                   help='Max age (days) of local data before new download is '
                   'made (default: %(default)s days)')
    p.add_argument('--no-cleanup', '-n', action='store_true', default=False,
                   help="Don't remove temporary data (default: %(default)s)")
    return p.parse_args()


if __name__ == '__main__':
    args = _parse_commandline()
    main(args.data_dir, max_data_age=args.max_age, cleanup=not args.no_cleanup)

