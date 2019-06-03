# -*- coding: utf-8 -*-

import re

from datetime import date

from utils import ParserSpec


SYMBOL_re = re.compile(r'GHS0\d')
STRIPS = '~ca. <>E'


def parse_temp_range(match):
    raw = match.group(1)
    if '-' in raw:
        try:
            return [float(x.strip(STRIPS).replace(',', '.'))
                    for x in raw.split('-')]
        except ValueError:
            pass
    return [float(raw.strip(STRIPS).replace(',', '.')), None]


def parse_density(match):
    ref_temp = int(match.group(1))
    try:
        density = float(match.group(2).strip(' ~').replace(',', '.'))
    except ValueError:
        return None
    return [density, ref_temp]


EXPRESSIONS = (
    ParserSpec(
        'review_date',
        r'überarbeitet.+?am\s+?(\d{1,2})\.(\d{1,2})\.(\d{2,4})', re.I,
        lambda m: date(int(m.group(3)), int(m.group(2)), int(m.group(1))),
        None
    ),
    ParserSpec('cas', r'CAS.Nr\.\s+?(\d{1,7}\-\d{2}\-\d)', re.I),
    ParserSpec('eg_num', 'EG.Nr\.\s+?(.+)', re.I),
    ParserSpec.simple('art_name', 'Artikelbezeichnung', ''),
    # Ab hier weiter bearbeiten
    ParserSpec('name', r'CAS\-.+?\s+?Bezeichnung\s+?.+?\s+?(.+)\n', re.I),
    ParserSpec.simple('art_num', 'Artikelnummer'),
    ParserSpec(
        'hazards_raw', r'2\.2\s+?Kennzeichnungselemente\n?(.+)2\.3\s+?Sonstige',
        re.I | re.S
    ),
    ParserSpec(
        'fire', r'5\s+?.+?mpfung\n?(.+)6\s+?Ma', re.I | re.S
    ),
    ParserSpec('signal', r'Signalwort\s+?(.+)\n', re.I),
    ParserSpec('params', r'8\.1\s+?Zu.+?\n(.+)8\.2\s+?', re.I | re.S),
    ParserSpec.simple('formula', 'Summenformel'),
    ParserSpec(
        'molmass', r'Molare.+?:\s+?(.+)\n', re.I,
        lambda m: float(m.group(1).replace(',', '.'))
    ),
    ParserSpec.simple('state', 'Form'),
    ParserSpec.simple('color', 'Farbe'),
    ParserSpec.simple('odor', 'Geruch'),
    ParserSpec('melting', r'Schmelzpunkt.+?:\s+?(.+)\s*?°C', re.I,
               parse_temp_range),
    ParserSpec('boiling', r'Siedepunkt.+?:\s+?(.+)\s*?°C', re.I,
               parse_temp_range),
    ParserSpec('density', r'Dichte.+?(\-?\d+?)\s*?°C:\s+?(.+)\s*?g/cm', re.I,
               parse_density, default=None),
    ParserSpec('bulk_density', r'Schüttdichte.+?(\-?\d+?)\s*?°C:\s+?(.+)\s*?kg/m',
               re.I, parse_density, default=None),
    ParserSpec('solubility_h2o', r'Löslichkeit.+\n.*?Wasser.+?(\d+).+:'
               r'\s+?(.+)\s*?g/l', re.I, parse_density),
    ParserSpec.simple('kemler', 'Kemler-Zahl'),
    ParserSpec.simple('betrsichv', '(BetrSichV)'),
    ParserSpec('lgk_trgs510', r'TRGS\s+?510:\n(.+?)\s', re.I),
    ParserSpec('wgk', r'WGK\s+?(\d)', re.I, lambda m: int(m.group(1))),
    ParserSpec('vwvws', r'VwVws:.+?(\d+)\n', re.I, lambda m: int(m.group(1))),
    ParserSpec('agw', r'AGW.+?:\s*?(.+)\s*?mg/m', re.I,
               lambda m: float(m.group(1).strip(STRIPS).replace(',', '.')),
               default=None),
    ParserSpec('bgw', r'BGW.+?([0-9.,]+)\s*?mg/l', re.I,
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
            data['h'].add(l.split()[0])
        elif l[0] == 'P' and l[1].isdigit():
            data['p'].add(l.split()[0])
        elif l[0] == 'E' and l[1] == 'U' and l[3].isdigit():
            data['euh'].add(l.split()[0])
    data['symbols'] = SYMBOL_re.findall(txt)
    data['h'] = list(data['h'])
    data['p'] = list(data['p'])
    data['euh'] = list(data['euh'])
    del data['hazards_raw']
    return data
    

def _parse_fire(data):
    txt = data['fire']
    data['ext_agents'] = ''
    data['no_ext_agents'] = ''
    data['fire_misc'] = ''
    for t in [x.strip() for x in txt.split(chr(183))]:
        if 'geeignete löschmittel' in t.lower():
            tmp = t.split(':', 1)[1].strip()
            data['ext_agents'] = re.sub(r'\s+', ' ', tmp)
        elif 'ungeeignete löschmittel' in t.lower():
            tmp = t.split(':', 1)[1].strip()
            data['no_ext_agents'] = re.sub(r'\s+', ' ', tmp)
        elif 'sonstige hinweise' in t.lower():
            tmp = t.split(':', 1)[1].strip()
            data['fire_misc'] = re.sub(r'\s+', ' ', tmp)
    del data['fire']
    return data


def parse(text):
    data = {}
    for spec in EXPRESSIONS:
        data[spec.id] = spec(text)
    data = _parse_dnel(data)
    data = _parse_hazards(data)
    data = _parse_fire(data)
    data['syn'] = []
    return data
