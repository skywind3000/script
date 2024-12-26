#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# shell.py - 
#
# Created by skywind on 2024/12/26
# Last Modified: 2024/12/26 16:58:21
#
#======================================================================
from __future__ import print_function, unicode_literals
import sys
import time
import os

try:
    from . import core
except ImportError:
    import core

UNIX = core.UNIX


#----------------------------------------------------------------------
# getopt
#----------------------------------------------------------------------
def getopt(argv):
    args = []
    options = {}
    if argv is None:
        argv = sys.argv[1:]
    index = 0
    count = len(argv)
    while index < count:
        arg = argv[index]
        if arg != '':
            head = arg[:1]
            if head != '-':
                break
            if arg == '-':
                break
            name = arg.lstrip('-')
            key, _, val = name.partition('=')
            options[key.strip()] = val.strip()
        index += 1
    while index < count:
        args.append(argv[index])
        index += 1
    return options, args



