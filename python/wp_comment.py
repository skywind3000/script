#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# wp_comment.py - 
#
# Created by skywind on 2025/10/18
# Last Modified: 2025/10/18 20:06:39
#
#======================================================================
import sys
import os
import shutil
import bs4
import cinit
import asclib
import asclib.posix
import asclib.core
import ascmini


#----------------------------------------------------------------------
# locations
#----------------------------------------------------------------------
def location(relpath, *args):
    LOCATION = 'E:/Site/recover'
    argv = [relpath] + list(args)
    return os.path.abspath(os.path.join(LOCATION, *argv))


#----------------------------------------------------------------------
# 
#----------------------------------------------------------------------
def skywind_inside_xml():
    fn = location('skywindinside.xml')
    content = asclib.posix.load_file_text(fn)
    return bs4.BeautifulSoup(content, 'lxml-xml')


#----------------------------------------------------------------------
# 
#----------------------------------------------------------------------
def skywind_inside_parse():
    soup = skywind_inside_xml()
    items = soup.find_all('item')
    comments = []
    for item in items:
        title = item.title.string
        link = item.link.string
        post_id = item.find('wp:post_id').string
        uuid = int(post_id)
        print(uuid, link)
    return comments


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        print(location('skywindinside.xml'))
        soup = skywind_inside_xml()
        skywind_inside_parse()
        return 0
    test1()


