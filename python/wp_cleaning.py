#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# wp_cleaning.py - 
#
# Created by skywind on 2025/10/21
# Last Modified: 2025/10/21 23:48:22
#
#======================================================================
import sys
import os
import time
import bs4
import cinit
import asclib
import wp_comment

from wp_comment import Comment, CommentManager
from wp_comment import location, ArchiveWebsite


#----------------------------------------------------------------------
# clean_content(content: str) 
#----------------------------------------------------------------------
def clean_content(content: str) -> str:
    cite = ''
    pos = content.find('<a href="#comment-')
    if pos >= 0:
        p2 = content.find('</a>', pos)
        if p2 >= 0:
            cite = content[pos:p2 + 4]
            content = content.replace(cite, '')
    print('<<<<')
    content = '\n'.join([ n.lstrip() for n in content.split('\n') ])
    soup = bs4.BeautifulSoup(content, 'lxml')
    content = soup.get_text()
    lines = content.split('\n')
    while len(lines) > 0:
        if lines[0].strip() == '':
            lines.pop(0)
        else:
            break
    while len(lines) > 0:
        if lines[-1].strip() == '':
            lines.pop()
        else:
            break
    content = '\n'.join(lines)
    content = asclib.string.text_to_html(content)
    if cite:
        content = cite.rstrip() + '\n' + content
    print(content)
    return content


#----------------------------------------------------------------------
# clean_content(content: str)
#----------------------------------------------------------------------
def analyse_comments(filename) -> int:
    cm = CommentManager()
    cm.load(filename)
    for key in cm:
        comment: Comment = cm[key]
        if comment.origin != 'export':
            content = comment.content
            if '<a' in content or '<p>' in content or '<br>' in content:
                comment.print()
                comment.content = clean_content(content)
                print('------------------')
    cm.save(location('comment_cleaned.json'))
    return 0


#----------------------------------------------------------------------
# 
#----------------------------------------------------------------------
def analyse_view_count():
    aw = ArchiveWebsite('e:/site/recover/website')
    aw.load_index()
    print(aw[3163]['filename'])
    for uuid in aw:
        item = aw[uuid]
        # print(uuid, item['filename'])
    return 0

#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        analyse_comments(location('comment_primitive.json'))
        return 0
    def test2():
        cm = CommentManager()
        cm.load(location('comment_cleaned.json'))
        print(len(cm))
        wp_comment.export_comments_to_csv(cm, location('comment_cleaned.csv'))
    def test3():
        analyse_view_count()
        return 0
    test3()



