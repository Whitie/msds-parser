#!/usr/bin/env python
# -*- coding: utf-8 -*-

import glob
import json
import os
import re
import shutil
import time

from argparse import ArgumentParser
from datetime import date
from subprocess import check_call, check_output
from tempfile import TemporaryDirectory

import pubchempy as pcp
import requests

import uba
import utils
import p_acros
import p_caelo
import p_roth
import p_merck
import p_sigma


if os.name == 'nt':
    GS_BIN = r'C:\Users\wet\Downloads\Ghostscript\bin\gswin64c.exe'
    TESS_BIN = r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
else:
    GS_BIN = 'gsc'
    TESS_BIN = 'tesseract'

_PATH = os.path.dirname(os.path.abspath(__file__))
STORE_PATH = os.path.join(_PATH, 'sdb_json')
PC_URL = 'https://pubchem.ncbi.nlm.nih.gov/'
PC_SEARCH = 'https://www.ncbi.nlm.nih.gov/pccompound'
PC_IMG = '{}image/imagefly.cgi'.format(PC_URL)
TRANSLATE_URL = 'http://translate.google.com/translate_a/t'
PARSERS = {
    'acros': p_acros,
    'caelo': p_caelo,
    'roth': p_roth,
    'merck': p_merck,
    'sigma': p_sigma,
}

TRANS = {
    'natriumhydrogencarbonat': 'sodium bicarbonate',
    'isopropylphenazon plv.': 'propyphenazone',
    'kresolrot': 'cresol red',
    'm-kresolpurpur': 'm-cresol purple',
}

GHS_SYM = {
    ('H200', 'H201', 'H202', 'H203', 'H204', 'H240'): set(['GHS01']),
    ('H241',): set(['GHS01', 'GHS02']),
    ('H220', 'H222', 'H223', 'H224', 'H225', 'H226', 'H228', 'H242', 'H250',
     'H251', 'H252', 'H260', 'H261'): set(['GHS02']),
    ('H270', 'H271', 'H272'): set(['GHS03']),
    ('H280', 'H281'): set(['GHS04']),
    ('H290', 'H314', 'H318'): set(['GHS05']),
    ('H300', 'H301', 'H310', 'H311', 'H330', 'H331'): set(['GHS06']),
    ('H302', 'H312', 'H315', 'H317', 'H319', 'H332', 'H335',
     'H336'): set(['GHS07']),
    ('H350', 'H350I', 'H351', 'H340', 'H341', 'H360', 'H360F', 'H360D', 'H361',
     'H361F', 'H361D', 'H370', 'H371', 'H372', 'H373', 'H334',
     'H304'): set(['GHS08']),
    ('H400', 'H410', 'H411'): set(['GHS09']),
}

MANUFACTURER_res = (
    re.compile(r'Hersteller.+:\s?(.+)\n', re.I),
    re.compile(r'Firma\s+?(.+)\s', re.I),
    re.compile(r'Firma\s*?\n(.+)\n', re.I),
    re.compile(r'Firma\s*?:\s*?(.+)\n', re.I),
    re.compile(r'Bezeichnung des Unternehmens\s*?(.+)\n', re.I),
    re.compile(r'Carl\s+?(Roth)\s+?GmbH', re.I),
)
PC_COMPOUND_re = re.compile(r'.+?/compound/(\d+)/?'.format(PC_URL), re.I)


def _run_tesseract(pdf_file):
    with TemporaryDirectory() as tmp:
        outname = os.path.join(tmp, 'scan_%03d.tif')
        cmd = [GS_BIN, '-dNOPAUSE', '-r300', '-sDEVICE=tiffscaled24',
               '-sCompression=lzw', '-dBATCH',
               '-sOutputFile={}'.format(outname), pdf_file]
        check_call(cmd)
        scans = glob.glob(os.path.join(tmp, 'scan_*.tif'))
        for scan in scans:
            outname = os.path.splitext(scan)[0]
            cmd = [TESS_BIN, scan, outname, '-l', 'deu']
            check_call(cmd)
        text_files = glob.glob(os.path.join(tmp, 'scan_*.txt'))
        text_files.sort()
        out = []
        for tf in text_files:
            with open(tf, encoding='utf-8') as fp:
                out.append(fp.read())
    return '\n'.join(out)


def generate_text(pdf_file):
    txt_file = '{}.txt'.format(pdf_file)
    if os.path.isfile(txt_file):
        with open(txt_file, encoding='utf-8') as fp:
            return fp.read()
    cmd = ['pdftotext', '-raw', '-nopgbrk', '-enc', 'UTF-8', pdf_file, '-']
    try:
        out = check_output(cmd)
        out = out.decode('utf-8', errors='replace')
        out = out.replace('\r', '\n').replace('\n\n', '\n')
    except Exception as err:
        print('pdftotext can not handle:', pdf_file)
        print('Error:', err)
        print('Trying tesseract...')
        try:
            out = _run_tesseract(pdf_file)
        except Exception as err:
            print('tesseract can not handle:', pdf_file)
            print('Error:', err)
            return ''
    with open(txt_file, 'w', encoding='utf-8') as fp:
        fp.write(out)
    return out


def get_modify_time(pdf_file):
    return os.stat(pdf_file).st_mtime


def get_manufacturer(text):
    for r in MANUFACTURER_res:
        m = r.search(text)
        if m is not None:
            return m.group(1).strip()
    return ''


def get_parse_module(manufacturer):
    m = manufacturer.lower()
    for manu, module in PARSERS.items():
        if manu in m:
            return module
    raise ValueError('Manufacturer ({}) not known'.format(manufacturer))


def _get_filename(f, outdir, ext='json'):
    _fn = os.path.split(f)[1]
    fn = os.path.splitext(_fn)[0]
    if fn.startswith('SDB'):
        fn = fn[3:].strip()
    store = os.path.join(outdir, fn[0].lower())
    if not os.path.isdir(store):
        os.makedirs(store)
    return os.path.join(store, '{} SDB.{}'.format(fn, ext))


def _get_structure(cid):
    data = dict(cid=cid, width='300', height='300')
    r = requests.get(PC_IMG, params=data)
    if r.status_code == 200:
        return r.content
    return ''


def _translate(text, trans):
    t = text.lower().strip()
    if t in TRANS:
        return TRANS[t]
    if t in trans:
        text = trans[t]
    params = dict(client='z', sl='de', tl='en', ie='UTF-8', oe='UTF-8',
                  text=text)
    r = requests.get(TRANSLATE_URL, params=params)
    if r.status_code != 200:
        return text
    data = r.json()
    return data


def request_pubchem(cas, name, en_name, trans):
    if en_name:
        en_name = _translate(en_name, trans)
    else:
        en_name = _translate(name.capitalize(), trans)
    cas = cas.strip()
    print(name, '-->', en_name, '(en), CAS: {}'.format(cas))
    if cas:
        r = requests.get(PC_SEARCH, params={'term': 'CAS-{}'.format(cas)})
    else:
        r = requests.get(PC_SEARCH, params={'term': en_name})
    m = PC_COMPOUND_re.search(r.url)
    data = {}
    structure = ''
    if m is not None:
        cid = m.group(1)
        compound = pcp.Compound.from_cid(int(cid))
        data = compound.to_dict()
        structure = _get_structure(cid)
    else:
        # Try the same with the translated name
        r = requests.get(PC_SEARCH, params={'term': en_name})
        m = PC_COMPOUND_re.search(r.url)
        if m is not None:
            cid = m.group(1)
            compound = pcp.Compound.from_cid(int(cid))
            data = compound.to_dict()
            structure = _get_structure(cid)
        else:
            try:
                compound = pcp.get_compounds(en_name, 'name')[0]
                data = compound.to_dict()
                structure = _get_structure(str(compound.cid))
            except IndexError:
                # Try to find as substance
                try:
                    substance = pcp.get_substances(en_name, 'name')[0]
                    compound = pcp.Compound.from_cid(substance.cids[0])
                    data = compound.to_dict()
                    structure = _get_structure(str(compound.cid))
                except IndexError:
                    pass
    return data, structure, en_name


def _combine_with_pubchem(data, pubchem):
    data['molmass'] = pubchem.get('molecular_weight', None)
    data['formula'] = pubchem.get('molecular_formula', '')
    data['smiles'] = pubchem.get('canonical_smiles', '')
    data['pc_cid'] = pubchem.get('cid', None)
    data['inchi'] = pubchem.get('inchi', '')
    data['inchikey'] = pubchem.get('inchikey', '')
    data['iupac_en'] = pubchem.get('iupac_name', '')
    data['iupac_de'] = ''
    return data


def _check_symbols(data):
    seth = set([x.upper() for x in data.get('h', [])])
    symbols = set()
    for hs, syms in GHS_SYM.items():
        for h in hs:
            if h in seth:
                symbols |= syms
    data['symbols'] = list(symbols)
    return data


def _update_from_uba(data, entry):
    data['cas'] = entry.get('cas', data['cas'])
    data['eg_num'] = entry.get('einecs', data['eg_num'])
    data['name'] = entry.get('name', data['name']).strip()
    data['name_en'] = entry.get('name_en', '').strip()
    data['wgk'] = entry.get('wgk', data['wgk'])
    if 'syn' not in data or not isinstance(data['syn'], list):
        data['syn'] = []
    data['syn'].extend(entry.get('synonyms', []))
    return data


def _check_uba(data, uba_data):
    data['cas'] = data.get('cas', '').strip()
    name = data['name'].lower()
    data['name_en'] = ''
    nc = uba_data['name_cas']
    nec = uba_data['name_en_cas']
    ca = uba_data['cas_all']
    if data['cas']:
        if data['cas'] in ca:
            print('UBA:', data['cas'], 'found.')
            data = _update_from_uba(data, ca[data['cas']])
    else:
        if name in nc:
            cas = nc[name]
            print('UBA:', name, 'found -->', cas)
            data = _update_from_uba(data, ca[cas])
        elif name in nec:
            cas = nec[name]
            print('UBA:', name, 'found -->', cas)
            data = _update_from_uba(data, ca[cas])
    return data


def run(filename, outdir, force=False, uba_data=None):
    uba_data = uba_data or {}
    new_filename = _get_filename(filename, outdir)
    if os.path.isfile(new_filename):
        if not force:
            return
        else:
            os.remove(new_filename)
    txt = generate_text(filename)
    man = get_manufacturer(txt)
    try:
        mod = get_parse_module(man)
    except ValueError as err:
        print(err, filename)
        return
    data = mod.parse(txt)
    data['producer'] = man
    data['source'] = filename
    data = _check_symbols(data)
    data = _check_uba(data, uba_data)
    print(ascii(data))
    if not data['name']:
        data['name'] = data['art_name'].split()[0].capitalize()
    try:
        pubchem, structure, en = request_pubchem(data['cas'], data['name'],
                                                 data['name_en'],
                                                 uba_data['name_de_en'])
    except:
        pubchem = {}
        structure = ''
        en = ''
    if not data['name_en']:
        data['name_en'] = en
    if isinstance(data['review_date'], date):
        data['review_date'] = data['review_date'].strftime('%Y-%m-%d')
    else:
        data['review_date'] = str(data['review_date'])
    if structure:
        st_name = _get_filename(filename, outdir, 'png')
        if not os.path.isfile(st_name):
            with open(st_name, 'wb') as fp:
                fp.write(structure)
        data['structure'] = st_name
    else:
        data['structure'] = ''
    # Combine with pubchem entry
    data = _combine_with_pubchem(data, pubchem)
    data['h'].sort()
    data['p'].sort()
    data['euh'].sort()
    synonyms = set()
    for s in data.pop('syn', []):
        if len(s) > 3:
            synonyms.add(s.strip())
    data['synonyms'] = list(synonyms)
    with open(new_filename, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, indent=2, sort_keys=True)
    return data


def _get_sdb_files(sdb_directories):
    filenames = []
    for d in sdb_directories:
        sdb_path = os.path.abspath(d)
        for f in glob.glob(os.path.join(sdb_path, '*.pdf')):
            filenames.append(f)
    return filenames


def main(sdb_files, outdir=STORE_PATH, force=False):
    all_data = []
    uba_data = uba.main(outdir)
    path = os.path.dirname(os.path.abspath(__file__))
    for f in sdb_files:
        parsed_data = run(f, outdir, force, uba_data)
        if parsed_data:
            all_data.append(parsed_data)
    with open(os.path.join(outdir, 'all.json'), 'w', encoding='utf-8') as fp:
        json.dump(all_data, fp, indent=2, sort_keys=True)


def _parse_commandline():
    p = ArgumentParser(description='Extract and parse the text from a german '
                       'SDB (PDF format) and collect information on '
                       'the substance.')
    p.add_argument('directories', nargs='+', help='Directories to search for '
                   "SDB's")
    p.add_argument('--force', '-f', action='store_true', default=False,
                   help='Force the extraction of already extracted content '
                   '(default: %(default)s)')
    p.add_argument('--outdir', '-o', default=STORE_PATH, help='Directory to '
                   'store the resulting JSON files in (default: %(default)s)')
    p.add_argument('--uba-file', '-u', default=None, help='Use existing '
                   'uba.json file (give path here). Default is to download '
                   'new data.')
    return p.parse_args()


def batch_call(outdir, directories, force=False, uba_file=None):
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    files = _get_sdb_files(directories)
    if uba_file is not None and os.path.isfile(uba_file):
        shutil.copy2(uba_file, outdir)
    main(files, outdir, force)


if __name__ == '__main__':
    start = time.time()
    args = _parse_commandline()
    batch_call(args.outdir, args.directories, args.force, args.uba_file)
    end = time.time()
    minutes, seconds = divmod(end - start, 60)
    print('Duration: {}min {:.1f}s'.format(int(minutes), seconds))
