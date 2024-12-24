#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# regex.py - 
#
# Created by skywind on 2024/12/24
# Last Modified: 2024/12/24 15:27:01
#
#======================================================================
from __future__ import unicode_literals, print_function
import sys
import re


#----------------------------------------------------------------------
# all
#----------------------------------------------------------------------
__all__ = ['build', 'expand']


#----------------------------------------------------------------------
# replace {name} dotation in pattern with macros
#----------------------------------------------------------------------
def expand(macros, pattern, guarded = True):
    output = []
    pos = 0
    size = len(pattern)
    while pos < size:
        ch = pattern[pos]
        if ch == '\\':
            output.append(pattern[pos:pos + 2])
            pos += 2
            continue
        elif ch != '{':
            output.append(ch)
            pos += 1
            continue
        p2 = pattern.find('}', pos)
        if p2 < 0:
            output.append(ch)
            pos += 1
            continue
        p3 = p2 + 1
        name = pattern[pos + 1:p2].strip('\r\n\t ')
        if name == '':
            output.append(pattern[pos:p3])
            pos = p3
            continue
        elif name[0].isdigit():
            output.append(pattern[pos:p3])
            pos = p3
            continue
        elif ('<' in name) or ('>' in name):
            raise ValueError('invalid pattern name "%s"'%name)
        if name not in macros:
            raise ValueError('{%s} is undefined'%name)
        if guarded:
            output.append('(?:' + macros[name] + ')')
        else:
            output.append(macros[name])
        pos = p3
    return ''.join(output)


#----------------------------------------------------------------------
# build complex regex rules
#----------------------------------------------------------------------
def build(code, macros = None, capture = True):
    defined = {}
    if macros is not None:
        for k, v in macros.items():
            defined[k] = v
    line_num = 0
    for line in code.split('\n'):
        line_num += 1
        line = line.strip('\r\n\t ')
        if (not line) or line.startswith('#'):
            continue
        pos = line.find('=')
        if pos < 0:
            raise ValueError('%d: not a valid rule'%line_num)
        head = line[:pos].strip('\r\n\t ')
        body = line[pos + 1:].strip('\r\n\t ')
        if (not head):
            raise ValueError('%d: empty rule name'%line_num)
        elif head[0].isdigit():
            raise ValueError('%d: invalid rule name "%s"'%(line_num, head))
        elif ('<' in head) or ('>' in head):
            raise ValueError('%d: invalid rule name "%s"'%(line_num, head))
        try:
            pattern = expand(defined, body, guarded = not capture)
        except ValueError as e:
            raise ValueError('%d: %s'%(line_num, str(e)))
        try:
            re.compile(pattern)
        except re.error:
            raise ValueError('%d: invalid pattern "%s"'%(line_num, pattern))
        if not capture:
            defined[head] = pattern
        else:
            defined[head] = '(?P<%s>%s)'%(head, pattern)
    return defined


#----------------------------------------------------------------------
# tokenize
#----------------------------------------------------------------------
def tokenize(code, specs, eof = None):
    patterns = []
    definition = {}
    extended = {}
    if not specs:
        return None
    for index in range(len(specs)):
        spec = specs[index]
        name, pattern = spec[:2]
        pn = 'PATTERN%d'%index
        definition[pn] = name
        if len(spec) >= 3:
            extended[pn] = spec[2]
        patterns.append((pn, pattern))
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in patterns)
    line_starts = []
    pos = 0
    index = 0
    while 1:
        line_starts.append(pos)
        pos = code.find('\n', pos)
        if pos < 0:
            break
        pos += 1
    line_num = 0
    for mo in re.finditer(tok_regex, code):
        kind = mo.lastgroup
        value = mo.group()
        start = mo.start()
        while line_num < len(line_starts) - 1:
            if line_starts[line_num + 1] > start:
                break
            line_num += 1
        line_start = line_starts[line_num]
        name = definition[kind]
        if name is None:
            continue
        if callable(name):
            if kind not in extended:
                obj = name(value)
            else:
                obj = name(value, extended[kind])
            name = None
            if isinstance(obj, list) or isinstance(obj, tuple):
                if len(obj) > 0: 
                    name = obj[0]
                if len(obj) > 1:
                    value = obj[1]
            else:
                name = obj
        yield (name, value, line_num + 1, start - line_start + 1)
    if eof is not None:
        line_start = line_starts[-1]
        endpos = len(code)
        yield (eof, '', len(line_starts), endpos - line_start + 1)
    return 0


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':

    def test1():
        rules = r'''
            protocol = http|https|trojan|ss
            login_name = [^:@\r\n\t ]+
            login_pass = [^@\r\n\t ]+
            login = {login_name}(:{login_pass})?
            host = [^:/@\r\n\t ]+
            port = \d+
            optional_port = (?:[:]{port})?
            path = [\/\?][^\r\n\t ]*
            url = {protocol}://({login}[@])?{host}{optional_port}{path}?
        '''
        m = build(rules, capture = True)
        pattern = m['url']
        s = re.match(pattern, 'https://name:pass@www.baidu.com:8080/haha')
        print('matched: "%s"'%s.group(0))
        print()
        for name in ('login_name', 'login_pass', 'host', 'port', 'path'):
            print('subgroup:', name, '=', s.group(name))
        return 0

    def test2():
        code = '''
            IF quantity THEN
                total := total + price * quantity;
                tax := price * 0.05;
            ENDIF;
            '''
        keywords = {'IF', 'THEN', 'ENDIF', 'FOR', 'NEXT', 'GOSUB', 'RETURN'}
        def check_name(text):
            if text.upper() in keywords:
                return text.upper()
            return 'NAME'
        rules = [
                (None,       r'[ \t]+'),
                ('NUMBER',   r'\d+(\.\d*)?'),
                ('ASSIGN',   r':='),
                ('END',      r';'),
                (check_name, r'[A-Za-z]+'),
                ('OP',       r'[+\-*/]'),
                ('NEWLINE',  r'\n'),
                ('MISMATCH', r'.'),
                ]
        for token in tokenize(code, rules, None):
            print(token)
        return 0

    test2()


