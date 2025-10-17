#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# wp_recover.py - 
#
# Created by skywind on 2025/10/17
# Last Modified: 2025/10/17 14:58:21
#
#======================================================================
import sys
import os
import cinit
import asclib
import asclib.posix


#----------------------------------------------------------------------
# parse markdown header
#----------------------------------------------------------------------
def md_header(content):
    mode = 0
    header = {}
    for line in content.split('\n'):
        line = line.strip('\r\n\t ')
        if not line:
            continue
        if line.startswith('-'):
            if line == '-' * len(line):
                if mode == 0:
                    mode = 1
                elif mode == 1:
                    break
        elif mode == 1:
            pos = line.find(':')
            if pos < 0:
                continue
            key = line[0:pos].strip('\r\n\t ').lower()
            val = line[pos + 1:].strip('\r\n\t ')
            if key:
                header[key] = val
    return header


#----------------------------------------------------------------------
# load header from markdown file
#----------------------------------------------------------------------
def md_info(filename):
    content = asclib.posix.load_file_text(filename)
    if not content:
        return None
    return md_header(content)


#----------------------------------------------------------------------
# locations
#----------------------------------------------------------------------
LOCATION_WORDPRESS = 'e:/site/wordpress/content'
LOCATION_CONTENT = 'e:/site/recover/content'
LOCATION_LEGACY = 'e:/site/recover/legacy'
LOCATION_OUTPUT = 'e:/site/recover/output'


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        print(md_info(LOCATION_WORDPRESS + '/2002/vmbasic.md'))
        return 0
    test1()




