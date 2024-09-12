#! /usr/bin/env python
# -*- coding: utf-8 -*-
#======================================================================
#
# findfiles.py - 
#
# Created by skywind on 2024/09/12
# Last Modified: 2024/09/12 10:20:24
#
#======================================================================
import sys
import os
import pathset
# pylint: disable-next=wrong-import-order
import ascmini
import cinit

def test1():
    for n in ascmini.posix.find_files('e:/site/skywind3000.github.io', '*.png', True):
        with open(n, 'rb') as fp:
            head = fp.read(2)
            if head == b'BM':
                print('bmp file:', n)
    return 0

def test2():
    for n in ascmini.posix.find_files('e:/site/images', '*.jpg', True):
        print(n)
    return 0

test2()


