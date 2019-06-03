# -*- coding: utf-8 -*-

import re


def validate_cas(cas_nr):
    if isinstance(cas_nr, list):
        cas_nr = cas_nr[0]
    try:
        cas_nr = cas_nr.split()[0]
    except IndexError:
        pass
    try:
        parts = cas_nr.split('-')[:2]
        nr = ''.join(parts)
        _check = 0
        for pos, num in enumerate(map(int, reversed(nr)), start=1):
            _check += pos * num
        check = _check % 10
        parts.append(str(check))
        return '-'.join(parts)
    except:
        return ''


class ParserSpec:

    def __init__(self, id, regex, flags=0, func=None, default=''):
        self.id = id
        self.regex = regex
        self.func = func
        self.flags = flags
        self.default = default
        self.compiled_re = re.compile(regex, flags)

    @classmethod
    def simple(cls, id, field, sep=':'):
        regex = r'\n{}{}\s+?(.+)\n'.format(re.escape(field), sep)
        return cls(id, regex, re.I)

    def __call__(self, text):
        match = self.compiled_re.search(text)
        if match is not None:
            if self.func is not None:
                return self.func(match)
            else:
                return match.group(1)
        return self.default
