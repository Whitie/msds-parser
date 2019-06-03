#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import json
import os
import sys

from zipfile import ZipFile


def load_data(filename):
    with open(filename, encoding='utf-8') as fp:
        data = json.load(fp)
    return data


def write_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, indent=2, sort_keys=True)


def prepare_data(data, outdir):
    new_data = []
    sdbs = ZipFile(os.path.join(outdir, 'sdbs.zip'), 'w')
    structures = ZipFile(os.path.join(outdir, 'structures.zip'), 'w')
    for chem in data:
        if not chem:
            continue
        if chem['h']:
            chem['h'] = [x.replace('H', '') for x in chem['h']]
        if chem['p']:
            chem['p'] = [x.replace('P', '') for x in chem['p']]
        if chem['euh']:
            chem['euh'] = [x.replace('EUH', '') for x in chem['euh']]
        if chem['symbols']:
            chem['symbols'] = [int(x.replace('GHS', '')) for x in
                               chem['symbols']]
        if chem['source']:
            name = os.path.basename(chem['source'])
            sdbs.write(chem['source'], name)
            chem['source'] = name
        if chem['structure']:
            name = os.path.basename(chem['structure'])
            structures.write(chem['structure'], name)
            chem['structure'] = name
        new_data.append(chem)
    sdbs.close()
    structures.close()
    write_data(os.path.join(outdir, 'all_cleaned.json'), new_data)


def main(infile, outdir):
    data = load_data(infile)
    new = prepare_data(data, outdir)


if __name__ == '__main__':
    try:
        main(sys.argv[1], sys.argv[2])
    except:
        print('Usage: {} INFILE OUTDIR'.format(sys.argv[0]))
        raise
