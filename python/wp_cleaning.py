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
import csv
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
# 
#----------------------------------------------------------------------
def pvc_analyse_json():
    array = asclib.state.load_json(location('website/index.json'))
    items = {}
    pattern1 = 'blog/wp-json/pvc/v1/increase'
    pattern2 = 'blog/wp-json/pvc/v1/view'
    for item in array:
        urls = item['urls']
        for key in urls:
            obj = urls[key]
            url = obj['url']
            if (pattern1 not in url) and (pattern2 not in url):
                continue
            pos = url.rfind('/')
            if pos < 0:
                continue
            assert(obj['folder'] == 'html')
            text = url[pos + 1:]
            name = obj['filename']
            fn = os.path.join(location('website/html', name))
            data = asclib.state.load_json(fn)
            assert(data['success'] == True)
            for key in data['items']:
                info = data['items'][key]
                uuid = info['post_id']
                view = info['total_view']
                if uuid not in items:
                    items[uuid] = view
                else:
                    previous = items[uuid]
                    if view > previous:
                        items[uuid] = view
    return items


#----------------------------------------------------------------------
# 
#----------------------------------------------------------------------
def pvc_analyse_count():
    items = pvc_analyse_json()
    fn = 'g:/download/firefox/wp_pvc_total.csv'
    index = {}
    with open(fn, 'r', encoding='utf-8') as f:
        csv_reader = csv.reader(f)
        next(csv_reader)
        for row in csv_reader:
            print(row)
            uuid = int(row[1])
            pvc = int(row[0])
            index[uuid] = pvc
    for uuid in items:
        if uuid not in index:
            print('missing', uuid)
            index[uuid] = len(index) + 1
    fn = location('wp_pvc_total.csv')
    with open(fn, 'w', encoding = 'utf-8') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(["id", "postnum", "postcount"])
        for uuid in index:
            pvc = index[uuid]
            if uuid not in items:
                print('missing count', uuid)
                continue
            count = items[uuid]
            test = location('combine/%d.md'%uuid)
            if not os.path.exists(test):
                print('skip uuid', uuid)
                continue
            csv_writer.writerow([str(pvc), str(uuid), str(count)])
    # for uuid in items:
    #     print(uuid, items[uuid])
    # print('total', len(items))
    return 0


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        analyse_comments(location('comment_merged.json'))
        return 0
    def test2():
        cm = CommentManager()
        cm.load(location('comment_cleaned.json'))
        print(len(cm))
        wp_comment.export_comments_to_csv(cm, location('comment_cleaned.csv'))
    def test3():
        analyse_view_count()
        return 0
    def test4():
        pvc_analyse_count()
        return 0
    test4()



