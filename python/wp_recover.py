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
import shutil
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
# split markdown header and body
#----------------------------------------------------------------------
def md_split(content):
    mode = 0
    header_lines = []
    body_lines = []
    for line in content.split('\n'):
        line = line.rstrip('\r\n\t ')
        if mode == 0:
            if not line:
                continue
            if line.startswith('-'):
                if line == '-' * len(line):
                    mode = 1
                    continue
        elif mode == 1:
            if line.startswith('-'):
                if line == '-' * len(line):
                    mode = 2
                    continue
            else:
                header_lines.append(line)
        elif mode == 2:
            if not line:
                continue
            mode = 3
        if mode == 3:
            body_lines.append(line)
    header = '\n'.join(header_lines)
    body = '\n'.join(body_lines)
    return header, body


#----------------------------------------------------------------------
# load header from markdown file
#----------------------------------------------------------------------
def md_info(filename):
    content = asclib.posix.load_file_text(filename)
    if not content:
        return None
    return md_header(content)


#----------------------------------------------------------------------
# 
#----------------------------------------------------------------------
def datetime_to_local(utc_time_str):
    from datetime import datetime, timezone, timedelta
    utc_time_str = utc_time_str.replace('Z', '+00:00')
    utc_dt = datetime.fromisoformat(utc_time_str)
    local_dt = utc_dt.astimezone()
    return local_dt.strftime('%Y-%m-%d %H:%M:%S')


#----------------------------------------------------------------------
# 
#----------------------------------------------------------------------
def sort_numberic(names):
    output = []
    for name in names:
        base, ext = os.path.splitext(name)
        try:
            num = int(base)
        except:
            num = 0
        output.append( (num, name) )
    output.sort()
    return [ x[1] for x in output ]


#----------------------------------------------------------------------
# locations
#----------------------------------------------------------------------
LOCATION_WORDPRESS = 'e:/site/wordpress/content'
LOCATION_RECOVER = 'e:/site/recover'
LOCATION_CONTENT = 'e:/site/recover/content'
LOCATION_LEGACY = 'e:/site/recover/legacy'
LOCATION_OUTPUT = 'e:/site/recover/output'


#----------------------------------------------------------------------
# convert wordpress content
#----------------------------------------------------------------------
def wp_convert_content():
    count = 0
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
                return 0
            print(fullpath, uuid, info.get('date'))
            dst = os.path.join(LOCATION_CONTENT, str(uuid) + '.md')
            shutil.copyfile(fullpath, dst)
            count += 1
    print('total files:', count)
    return 0


#----------------------------------------------------------------------
# convert legacy wordpress content
#----------------------------------------------------------------------
def wp_convert_legacy():
    for fn in os.listdir(LOCATION_LEGACY):
        if not fn.lower().endswith('.md'):
            continue
        fullpath = os.path.join(LOCATION_LEGACY, fn)
        content = asclib.posix.load_file_text(fullpath)
        if not content:
            print('suck')
            break
        header, body = md_split(content)
        info = md_header(content)
        uuid = int(os.path.splitext(fn)[0])
        url = info['url'].strip()
        rpos = url.rfind('/')
        if rpos >= 0:
            last = int(url[rpos + 1:].strip())
            if last != uuid:
                print('uuid mismatch:', uuid, last)
                break
        ni = {}
        ni['uuid'] = str(uuid)
        ni['title'] = eval(info['title'])
        ni['status'] = 'publish'
        ni['date'] = datetime_to_local(eval(info['date']))
        if 'categories' in info:
            cat = eval(info['categories'])
            ni['categories'] = ','.join(cat)
        if 'tags' in info:
            tag = eval(info['tags'])
            tt = []
            for t in tag:
                if t == 'Dos':
                    t = 'DOS'
                tt.append(t)
            ni['tags'] = ','.join(tt)
        print(ni)
        cc = []
        cc.append('---')
        for k in ni:
            cc.append(f'{k}: {ni[k]}')
        cc.append('---')
        for line in body.split('\n'):
            cc.append(line)
        out = os.path.join(LOCATION_OUTPUT, str(uuid) + '.md')
        asclib.posix.save_file_text(out, '\n'.join(cc))
    return 0


#----------------------------------------------------------------------
# 
#----------------------------------------------------------------------
def verify_post_uuid():
    fn = LOCATION_RECOVER + '/post_list.txt'
    content = asclib.posix.load_file_text(fn)
    count = 0
    for line in content.split('\n'):
        line = line.rstrip('\r\n\t ')
        if not line:
            continue
        part = line.split('\t')
        if len(part) < 2:
            continue
        try:
            uuid = int(part[0].strip())
        except:
            continue
        title = part[1]
        test_uuid = ''
        if '-' in title:
            pos = title.rfind('-')
            test_uuid = title[pos + 1:].strip()
        if test_uuid != str(uuid):
            print('mismatch:', uuid, test_uuid, title)
        print(part)
        count += 1
    print('total posts:', count)
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
    def test3():
        wp_convert_legacy()
        print(datetime_to_local('2001-04-10T07:04:52Z'))
        return 0
    def test4():
        for fn in os.listdir(LOCATION_CONTENT):
            fullpath = os.path.join(LOCATION_CONTENT, fn)
            info = md_info(fullpath)
            uuid = str(info['uuid'])
            test = os.path.join(LOCATION_OUTPUT, uuid + '.md')
            if os.path.exists(test):
                print('duplicated: ', fn, info['title'])
    def test5():
        names = []
        for fn in os.listdir(LOCATION_RECOVER + '/convert'):
            if not fn.lower().endswith('.md'):
                continue
            names.append(fn)
        names = sort_numberic(names)
        fp = open(LOCATION_RECOVER + '/init_posts.sh', 'w')
        for fn in names:
            fullname = os.path.join(LOCATION_RECOVER + '/convert', fn)
            info = md_info(fullname)
            uuid = info['uuid']
            date = info['date']
            text = 'wp post create'
            text += f' --import_id={uuid}'
            text += f' --post_type=post'
            text += f' --post_status=publish'
            text += f' --post_date="{date}" --post_title="TITLE-{uuid}"'
            text += f' --post_content="content"'
            fp.write(text + '\n')
            print(text)
        return 0
    def test6():
        verify_post_uuid()
        return 0
    test6()




