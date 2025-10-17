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
# convert wordpress content
#----------------------------------------------------------------------
def wp_convert_content():
    for root, dirs, files in os.walk(LOCATION_WORDPRESS):
        for f in files:
            if not f.lower().endswith('.md'):
                continue
            fullpath = os.path.join(root, f)
            info = md_info(fullpath)
            if not info:
                continue
            if 'uuid' not in info:
                print('error: no uuid:', fullpath)
                print(info)
                return 0
            uuid = int(info.get('uuid'))
            if 'date' not in info:
                print('error: no date:', fullpath)
                print(info)
                # return 0
            print(fullpath, uuid, info.get('date'))
    return 0


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        print(md_info(LOCATION_WORDPRESS + '/2002/vmbasic.md'))
        return 0
    def test2():
        wp_convert_content()
        return 0
    test2()




