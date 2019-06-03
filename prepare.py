#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import json
import os
import sys


CMR_HAZARDS = ('340', '341', '350', '351', '360', '361', '362', '372')


def load_data(filename):
    with open(filename, encoding='utf-8') as fp:
        data = json.load(fp)
    return data


def write_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, indent=2, sort_keys=True)


def check_cmr(hazard):
    for h in CMR_HAZARDS:
        if hazard.startswith(h):
            return True
    return False


def prepare_data(chem, outdir):
    if not chem:
        return
    chem['cmr'] = False
    chem['structure_fn'] = ''
    if chem['h']:
        chem['h'] = [x.replace('H', '') for x in chem['h']]
        chem['cmr'] = any([check_cmr(x) for x in chem['h']])
    if chem['p']:
        chem['p'] = [x.replace('P', '') for x in chem['p']]
    if chem['euh']:
        chem['euh'] = [x.replace('EUH', '') for x in chem['euh']]
    if chem['symbols']:
        chem['symbols'] = [int(x.replace('GHS', '')) for x in
                           chem['symbols']]
    if chem['source']:
        del chem['source']
    if chem['structure']:
        with open(chem['structure'], 'rb') as fp:
            data = fp.read()
        chem['structure_fn'] = os.path.basename(chem['structure'])
        chem['structure'] = base64.b64encode(data).decode('ascii')
    if chem['formula']:
        chem['formula'] = chem['formula'].replace(' ', '')
    if chem['signal']:
        sig = chem['signal'].lower()
        if sig == 'gefahr':
            chem['signal'] = 'danger'
        elif sig == 'achtung':
            chem['signal'] = 'warning'
    if not chem['boiling'] or isinstance(chem['boiling'], str):
        chem['boiling'] = [None, None]
    if not chem['melting'] or isinstance(chem['melting'], str):
        chem['melting'] = [None, None]
    if not chem['density']:
        chem['density'] = [None, None]
    if not chem['solubility_h2o']:
        chem['solubility_h2o'] = [None, None]
    if not chem['vwvws']:
        chem['vwvws'] = None
    write_data(os.path.join(outdir, 'single_chem.json'), chem)


def main(infile, outdir):
    data = load_data(infile)
    new = prepare_data(data, outdir)


if __name__ == '__main__':
    try:
        main(sys.argv[1], sys.argv[2])
    except:
        print('Usage: {} INFILE OUTDIR'.format(sys.argv[0]))
        raise
