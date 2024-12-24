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
        for name in ('url', 'login_name', 'login_pass', 'host', 'port', 'path'):
            print('subgroup:', name, '=', s.group(name))
        return 0
    test1()


