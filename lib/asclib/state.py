#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# state.py - 
#
# Created by skywind on 2024/12/24
# Last Modified: 2024/12/24 14:26:45
#
#======================================================================
from __future__ import print_function, unicode_literals
import sys
import os
import json
import pickle

try:
    from . import core
    from . import posix
except ImportError:
    import core
    import posix

UNIX = core.UNIX


#----------------------------------------------------------------------
# ini
#----------------------------------------------------------------------
def load_ini(filename, encoding = None):
    text = posix.load_file_text(filename, encoding)
    config = {}
    sect = 'default'
    if text is None:
        return None
    for line in text.split('\n'):
        line = line.strip('\r\n\t ')
        # pylint: disable-next=no-else-continue
        if not line:   # noqa
            continue
        elif line[:1] in ('#', ';'):
            continue
        elif line.startswith('['):
            if line.endswith(']'):
                sect = line[1:-1].strip('\r\n\t ')
                if sect not in config:
                    config[sect] = {}
        else:
            pos = line.find('=')
            if pos >= 0:
                key = line[:pos].rstrip('\r\n\t ')
                val = line[pos + 1:].lstrip('\r\n\t ')
                if sect not in config:
                    config[sect] = {}
                config[sect][key] = val
    return config


#----------------------------------------------------------------------
# save ini text
#----------------------------------------------------------------------
def __safe_ini_text(text):
    text = text.strip('\r\n\t ').replace('\n', '').replace('\r', '')
    return text.replace('=', '')


#----------------------------------------------------------------------
# save ini 
#----------------------------------------------------------------------
def save_ini(filename, config, atomic = False):
    output = []
    sectnames = ['default']
    for sect in config:
        if sect != 'default':
            sectnames.append(sect)
    for sectname in sectnames:
        if sectname not in config:
            continue
        output.append('[%s]' % __safe_ini_text(sectname))
        for key in config[sectname]:
            val = config[sectname][key]
            key = __safe_ini_text(key)
            val = __safe_ini_text(val)
            output.append('%s=%s' % (key, val))
        output.append('')
    text = '\n'.join(output)
    if atomic:
        if not posix.save_file_text_atomic(filename, text):
            return False
    if not posix.save_file_text(filename, text):
        return False
    return True


#----------------------------------------------------------------------
# json load
#----------------------------------------------------------------------
def load_json(filename, encoding = None):
    try:
        text = posix.load_file_text(filename, encoding)
        if text is None:
            return None
        return json.loads(text)
    except:
        return None
    return None


#----------------------------------------------------------------------
# json save 
#----------------------------------------------------------------------
def save_json(filename, obj, atomic = False):
    text = json.dumps(obj, indent = 4) + '\n'
    if not atomic:
        if not posix.save_file_text(filename, text):
            return False
    else:
        if not posix.save_file_text_atomic(filename, text):
            return False
    return True


#----------------------------------------------------------------------
# pickle load
#----------------------------------------------------------------------
def load_pickle(filename):
    with open(filename, 'rb') as fp:
        return pickle.load(fp)
    return None


#----------------------------------------------------------------------
# pickle save
#----------------------------------------------------------------------
def save_pickle(filename, obj, atomic = False):
    data = pickle.dumps(obj)
    if atomic:
        return posix.save_file_content_atomic(filename, data)
    return posix.save_file_content(filename, data)


