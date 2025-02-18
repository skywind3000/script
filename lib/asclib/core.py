#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# core.py - 
#
# Created by skywind on 2024/12/24
# Last Modified: 2024/12/24 13:47:00
#
#======================================================================
from __future__ import print_function, unicode_literals
import sys
import time
import os


#----------------------------------------------------------------------
# python 2/3 compatible
#----------------------------------------------------------------------
if sys.version_info[0] >= 3:
    long = int
    unicode = str

UNIX = (sys.platform[:3] != 'win') and True or False


#----------------------------------------------------------------------
# call program and returns output (combination of stdout and stderr)
#----------------------------------------------------------------------
def execute(args, shell = False, capture = False):
    import sys, os
    parameters = []
    cmd = None
    os.shell_return = -1
    if not isinstance(args, list):
        import shlex
        cmd = args
        if sys.platform[:3] == 'win':
            ucs = False
            if sys.version_info[0] < 3:
                if not isinstance(cmd, str):
                    cmd = cmd.encode('utf-8')
                    ucs = True
            args = shlex.split(cmd.replace('\\', '\x00'))
            args = [ n.replace('\x00', '\\') for n in args ]
            if ucs:
                args = [ n.decode('utf-8') for n in args ]
        else:
            args = shlex.split(cmd)
    for n in args:
        if sys.platform[:3] != 'win':
            replace = { ' ':'\\ ', '\\':'\\\\', '\"':'\\\"', '\t':'\\t',
                '\n':'\\n', '\r':'\\r' }
            text = ''.join([ replace.get(ch, ch) for ch in n ])
            parameters.append(text)
        else:
            # pylint: disable-next=else-if-used
            if (' ' in n) or ('\t' in n) or ('"' in n): 
                parameters.append('"%s"'%(n.replace('"', ' ')))
            else:
                parameters.append(n)
    if cmd is None:
        cmd = ' '.join(parameters)
    if sys.platform[:3] == 'win' and len(cmd) > 255:
        shell = False
    if shell and (not capture):
        os.shell_return = os.system(cmd)
        return b''
    elif (not shell) and (not capture):
        import subprocess
        if 'call' in subprocess.__dict__:
            os.shell_return = subprocess.call(args)
            return b''
    import subprocess
    if 'Popen' in subprocess.__dict__:
        argv = shell and cmd or args
        p = subprocess.Popen(argv, shell = shell,
                stdin = subprocess.PIPE, stdout = subprocess.PIPE, 
                stderr = subprocess.STDOUT)
        stdin, stdouterr = (p.stdin, p.stdout)
    else:
        p = None
        stdin, stdouterr = os.popen4(cmd)
    stdin.close()
    text = stdouterr.read()
    stdouterr.close()
    if p: p.wait()
    os.shell_return = -1
    if 'returncode' in p.__dict__:
        os.shell_return = p.returncode
    if not capture:
        sys.stdout.write(text)
        sys.stdout.flush()
        return b''
    return text


#----------------------------------------------------------------------
# call subprocess and returns retcode, stdout, stderr
#----------------------------------------------------------------------
def call(args, input_data = None, combine = False):
    import sys, os
    parameters = []
    for n in args:
        if sys.platform[:3] != 'win':
            replace = { ' ':'\\ ', '\\':'\\\\', '\"':'\\\"', '\t':'\\t', 
                '\n':'\\n', '\r':'\\r' }
            text = ''.join([ replace.get(ch, ch) for ch in n ])
            parameters.append(text)
        else:
            # pylint: disable-next=else-if-used
            if (' ' in n) or ('\t' in n) or ('"' in n):   # noqa
                parameters.append('"%s"'%(n.replace('"', ' ')))
            else:
                parameters.append(n)
    cmd = ' '.join(parameters)
    import subprocess
    bufsize = 0x100000
    if input_data is not None:
        if not isinstance(input_data, bytes):
            if sys.stdin and sys.stdin.encoding:
                input_data = input_data.encode(sys.stdin.encoding, 'ignore')
            elif sys.stdout and sys.stdout.encoding:
                input_data = input_data.encode(sys.stdout.encoding, 'ignore')
            else:
                input_data = input_data.encode('utf-8', 'ignore')
        size = len(input_data) * 2 + 0x10000
        if size > bufsize:
            bufsize = size
    if 'Popen' in subprocess.__dict__:
        p = subprocess.Popen(args, shell = False, bufsize = bufsize,
            stdin = subprocess.PIPE, stdout = subprocess.PIPE,
            stderr = combine and subprocess.STDOUT or subprocess.PIPE)
        stdin, stdout, stderr = p.stdin, p.stdout, p.stderr
        if combine: stderr = None
    else:
        p = None
        if combine is False:
            stdin, stdout, stderr = os.popen3(cmd)
        else:
            stdin, stdout = os.popen4(cmd)
            stderr = None
    if input_data is not None:
        stdin.write(input_data)
        stdin.flush()
    stdin.close()
    exeout = stdout.read()
    if stderr: exeerr = stderr.read()
    else: exeerr = None
    stdout.close()
    if stderr: stderr.close()
    retcode = None
    if p:
        retcode = p.wait()
    return retcode, exeout, exeerr


#----------------------------------------------------------------------
# redirect process output to reader(what, text)
#----------------------------------------------------------------------
def redirect(args, reader, combine = True):
    import subprocess
    parameters = []
    for n in args:
        if sys.platform[:3] != 'win':
            replace = { ' ':'\\ ', '\\':'\\\\', '\"':'\\\"', '\t':'\\t', 
                '\n':'\\n', '\r':'\\r' }
            text = ''.join([ replace.get(ch, ch) for ch in n ])
            parameters.append(text)
        else:
            # pylint: disable-next=else-if-used
            if (' ' in n) or ('\t' in n) or ('"' in n):     # noqa
                parameters.append('"%s"'%(n.replace('"', ' ')))
            else:
                parameters.append(n)
    cmd = ' '.join(parameters)
    if 'Popen' in subprocess.__dict__:
        p = subprocess.Popen(args, shell = False,
            stdin = subprocess.PIPE, stdout = subprocess.PIPE,
            stderr = combine and subprocess.STDOUT or subprocess.PIPE)
        stdin, stdout, stderr = p.stdin, p.stdout, p.stderr
        if combine: stderr = None
    else:
        p = None
        if combine is False:
            stdin, stdout, stderr = os.popen3(cmd)
        else:
            stdin, stdout = os.popen4(cmd)
            stderr = None
    stdin.close()
    while 1:
        text = stdout.readline()
        if text in (b'', ''):
            break
        reader('stdout', text)
    while stderr is not None:
        text = stderr.readline()
        if text in (b'', ''):
            break
        reader('stderr', text)
    stdout.close()
    if stderr: stderr.close()
    retcode = None
    if p:
        retcode = p.wait()
    return retcode


#----------------------------------------------------------------------
# OBJECT：enchanced object
#----------------------------------------------------------------------
class OBJECT (object):
    def __init__ (self, **argv):
        for x in argv: self.__dict__[x] = argv[x]
    def __getitem__ (self, x):
        return self.__dict__[x]
    def __setitem__ (self, x, y):
        self.__dict__[x] = y
    def __delitem__ (self, x):
        del self.__dict__[x]
    def __contains__ (self, x):
        return self.__dict__.__contains__(x)
    def __len__ (self):
        return self.__dict__.__len__()
    def __repr__ (self):
        line = [ '%s=%s'%(k, repr(v)) for k, v in self.__dict__.items() ]
        return 'OBJECT(' + ', '.join(line) + ')'
    def __str__ (self):
        return self.__repr__()
    def __iter__ (self):
        return self.__dict__.__iter__()


#----------------------------------------------------------------------
# call stack
#----------------------------------------------------------------------
def callstack ():
    import traceback
    if sys.version_info[0] < 3:
        import cStringIO
        sio = cStringIO.StringIO()
    else:
        import io
        sio = io.StringIO()
    traceback.print_exc(file = sio)
    return sio.getvalue()


#----------------------------------------------------------------------
# tabulify: style = 0, 1, 2
#----------------------------------------------------------------------
def tabulify(rows, style = 0):
    colsize = {}
    maxcol = 0
    output = []
    if not rows:
        return ''
    for row in rows:
        maxcol = max(len(row), maxcol)
        for col, text in enumerate(row):
            text = str(text)
            size = len(text)
            if col not in colsize:
                colsize[col] = size
            else:
                colsize[col] = max(size, colsize[col])
    if maxcol <= 0:
        return ''
    def gettext(row, col):
        csize = colsize[col]
        if row >= len(rows):
            return ' ' * (csize + 2)
        row = rows[row]
        if col >= len(row):
            return ' ' * (csize + 2)
        text = str(row[col])
        padding = 2 + csize - len(text)
        pad1 = 1
        pad2 = padding - pad1
        return (' ' * pad1) + text + (' ' * pad2)
    if style == 0:
        for y, row in enumerate(rows):
            line = ''.join([ gettext(y, x) for x in range(maxcol) ])
            output.append(line)
    elif style == 1:
        if rows:
            newrows = rows[:1]
            head = [ '-' * colsize[i] for i in range(maxcol) ]
            newrows.append(head)
            newrows.extend(rows[1:])
            rows = newrows
        for y, row in enumerate(rows):
            line = ''.join([ gettext(y, x) for x in range(maxcol) ])
            output.append(line)
    elif style == 2:
        sep = '+'.join([ '-' * (colsize[x] + 2) for x in range(maxcol) ])
        sep = '+' + sep + '+'
        for y, row in enumerate(rows):
            output.append(sep)
            line = '|'.join([ gettext(y, x) for x in range(maxcol) ])
            output.append('|' + line + '|')
        output.append(sep)
    return '\n'.join(output)


#----------------------------------------------------------------------
# hexdump
#----------------------------------------------------------------------
def hexdump(data, char = False):
    content = ''
    charset = ''
    lines = []
    if isinstance(data, str):
        if sys.version_info[0] >= 3:
            data = data.encode('utf-8', 'ignore')
    if not isinstance(data, bytes):
        raise ValueError('data must be bytes')
    for i, _ in enumerate(data):
        if sys.version_info[0] < 3:
            ascii = ord(data[i])
        else:
            ascii = data[i]
        if i % 16 == 0: content += '%08X  '%i
        content += '%02X'%ascii
        content += ((i & 15) == 7) and '-' or ' '
        # pylint: disable-next=chained-comparison
        if (ascii >= 0x20) and (ascii < 0x7f): charset += chr(ascii)
        else: charset += '.'
        if (i % 16 == 15): 
            lines.append(content + ' ' + charset)
            content, charset = '', ''
    if len(content) < 60: content += ' ' * (58 - len(content))
    lines.append(content + ' ' + charset)
    limit = char and 104 or 58
    return '\n'.join([ n[:limit] for n in lines ])


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        print('callstack:')
        print(callstack())
        return 0
    test1()


