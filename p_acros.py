# -*- coding: utf-8 -*-

import locale
import os
import re

from datetime import datetime, date

from utils import ParserSpec


SYMBOL_re = re.compile(r'GHS0\d')
STRIPS = '~ca. <>E'


if os.name.startswith('nt'):
    locale.setlocale(locale.LC_ALL, 'deu_deu')
else:
    locale.setlocale(locale.LC_ALL, 'de_DE.utf8')


def parse_temp_range(match):
    raw = match.group(1)
    if '-' in raw:
        try:
            return [float(x.strip(STRIPS).replace(',', '.'))
                    for x in raw.split('-')]
        except ValueError:
            pass
    elif '\u2013' in raw:
        try:
            return [float(x.strip(STRIPS).replace(',', '.'))
                    for x in raw.split('\u2013')]
        except ValueError:
            pass
    try:
        return [float(raw.strip(STRIPS).replace(',', '.')), None]
    except:
        return None

def parse_density(match):
    ref_temp = int(match.group(2))
    try:
        density = float(match.group(1).strip(STRIPS).replace(',', '.'))
    except ValueError:
        return None
    return [density, ref_temp]


def parse_density2(m):
    try:
        return [float(m.group(1).split()[0]), 20]
    except:
        return None


def parse_bulk_density(match):
    exp = match.group(1)
    if 'bis' in exp.lower():
        exp = exp.split('bis')[1].strip()
    try:
        return [float(exp.strip(STRIPS).replace(',', '.')), None]
    except:
        return None


def parse_float(m):
    num = m.group(1)
    try:
        return float(num.strip(STRIPS).replace(',', '.'))
    except ValueError:
        return None


EXPRESSIONS = (
    ParserSpec(
        'review_date',
        r'Überarbeitet am\s(\d{2}\-[a-z]{3}\-\d{4})\n', re.I,
        lambda m: datetime.strptime(m.group(1).strip(), '%d-%b-%Y').date(),
        None
    ),
    ParserSpec('cas', r'\n(\d{1,7}\-\d{2}\-\d)\n', re.I),
    ParserSpec('eg_num', r'EEC No\.\s*?(\d+\n?\-\n?\d+\n?\-\n?\d+)(\s|\n)',
               re.I, lambda m: m.group(1).replace('\n', '')),
    ParserSpec.simple('art_name', 'Produktname', ''),
    ParserSpec.simple('name', 'Produktname', ''),
    ParserSpec('syn', r'Synonyme\s+?(.+)\n', re.I,
               lambda m: [x.strip() for x in m.group(1).split(';')]),
    ParserSpec('art_num', '(ACR\d{4,9})\n', re.I),
    ParserSpec(
        'hazards_raw', r'2\.\s.+?\n(.+)3\.\s',
        re.I | re.S
    ),
    ParserSpec(
        'fire', r'ABSCHNITT\s+?5.+?\n(.+)\nABSCHNITT\s+?6', re.I | re.S
    ),
    ParserSpec.simple('signal', 'Signalwort', ''),
    ParserSpec('params', r'11\.\s(.+)12\.\s', re.I | re.S),
    ParserSpec.simple('formula', 'Summenformel', ''),
    ParserSpec('molmass', 'Molekulargewicht\s+?(.+)', re.I, parse_float),
    ParserSpec.simple('state', 'Aggregatzustand', ''),
    ParserSpec.simple('color', 'Aussehen', ''),
    ParserSpec.simple('odor', 'Geruch', ''),
    ParserSpec('melting', r'Schmelzpunkt.+?\s(.+)\s*?°\s*?C', re.I,
               parse_temp_range),
    ParserSpec('boiling', r'Siedepunkt.+?\s(.+)\s*?°\s*?C', re.I,
               parse_temp_range),
    ParserSpec('density', r'Spezifisches Gewicht\s+?(.+)\n', re.I,
               parse_density2, default=None),
    ParserSpec('bulk_density', r'Schüttdichte\s*?:\s+?(.+)\s*?kg/m',
               re.I, parse_bulk_density, default=None),
    ParserSpec('solubility_h2o', r'Wasserlöslichkeit\s+?(.+)\s*?g/L\s*?'
               r'\((\d+)\s*?°\s*?C\)', re.I, parse_density),
    ParserSpec.simple('kemler', 'Kemler-Zahl'),
    ParserSpec.simple('betrsichv', '(BetrSichV)'),
    ParserSpec('lgk_trgs510', r'Lagerklasse.+?:\s*?(.+)\n', re.I,
               lambda m: m.group(1).strip()),
    ParserSpec('wgk', r'WGK\s+?(\d)', re.I, lambda m: int(m.group(1))),
    ParserSpec('vwvws', r'VwVws:.+?(\d+)\n', re.I, lambda m: int(m.group(1))),
    ParserSpec('agw', r'AGW:?\s*?(.+)\s*?mg/m', re.I,
               lambda m: float(m.group(1).strip(STRIPS).replace(',', '.')),
               default=None),
    ParserSpec('bgw', r'BGW:?\s*?(.+)mg/l', re.I,
               lambda m: float(m.group(1).strip(STRIPS).replace(',', '.')),
               default=None),
    ParserSpec('ioelv', r'IOELV.+?:\s*?(.+)\s*?mg/m', re.I,
               lambda m: float(m.group(1).strip(STRIPS).replace(',', '.')),
               default=None),
)


def _parse_dnel(data):
    txt = data['params']
    del data['params']
    return data


def _parse_hazards(data):
    txt = data['hazards_raw']
    data['h'] = set()
    data['p'] = set()
    data['euh'] = set()
    for line in txt.split('\n'):
        l = line.strip()
        if len(l) < 4:
            continue
        if l[0] == 'H' and l[1].isdigit():
            h = l.split('-')[0]
            data['h'].add(h.strip())
        elif l[0] == 'P' and l[1].isdigit():
            p = l.split('-')[0]
            data['p'].add(p.replace(' ', '').strip())
        elif l[0] == 'E' and l[1] == 'U' and l[3].isdigit():
            euh = l.split('-')[0]
            data['euh'].add(euh.strip())
    data['h'] = list(data['h'])
    data['p'] = list(data['p'])
    data['euh'] = list(data['euh'])
    del data['hazards_raw']
    return data
    

def _parse_fire(data):
    txt = data['fire']
    fl = [x.strip() for x in txt.split('\n')]
    tmp = [x.lower() for x in fl]
    try:
        i = tmp.index('geeignete löschmittel')
        data['ext_agents'] = fl[i+1]
    except ValueError:
        data['ext_agents'] = ''
    try:
        j = tmp.index('aus sicherheitsgründen ungeeignete löschmittel')
        data['no_ext_agents'] = fl[j+1]
    except ValueError:
        data['no_ext_agents'] = ''
    try:
        k = tmp.index('hinweise für die brandbekämpfung')
        data['fire_misc'] = fl[k+1]
    except ValueError:
        data['fire_misc'] = ''
    del data['fire']
    return data


def parse(text):
    data = {}
    for spec in EXPRESSIONS:
        data[spec.id] = spec(text)
    data['symbols'] = SYMBOL_re.findall(text)
    data = _parse_dnel(data)
    data = _parse_hazards(data)
    data = _parse_fire(data)
    if not data['name']:
        data['name'] = data['art_name'].split(',')[0].capitalize()
    return data
