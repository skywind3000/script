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
import datetime
import bs4
import bs4.element
import cinit
import asclib
import asclib.posix
import asclib.core
import asclib.state
import asclib.string
import ascmini


#----------------------------------------------------------------------
# Comment
#----------------------------------------------------------------------
class Comment (object):

    def __init__ (self, uuid, cid, author, email, url, ip, date, content = None, user = 0, parent = 0):
        self.uuid = uuid
        self.cid = cid
        self.author = author
        self.email = email
        self.url = url
        self.ip = ip
        self.date = date
        self.content = content
        self.user = user
        self.parent = parent
        self.avatar = ''
        self.origin = ''

    def __repr__ (self):
        return '<Comment %d:%d %s>' % (self.uuid, self.cid, self.author)

    def to_dict (self):
        return {
            'uuid': self.uuid,
            'cid': self.cid,
            'author': self.author,
            'avatar': self.avatar,
            'email': self.email,
            'url': self.url,
            'ip': self.ip,
            'date': self.date,
            'content': self.content,
            'user': self.user,
            'parent': self.parent,
            'origin': self.origin,
        }

    def from_dict (self, obj):
        self.uuid = obj['uuid']
        self.cid = obj['cid']
        self.author = obj['author']
        self.avatar = obj.get('avatar', '')
        self.email = obj['email']
        self.url = obj['url']
        self.ip = obj['ip']
        self.date = obj['date']
        self.content = obj['content']
        self.user = obj['user']
        self.parent = obj['parent']
        self.origin = obj.get('origin', '')
        return self

    def stringify (self):
        lines = []
        lines.append('Comment %d on Post %d' % (self.cid, self.uuid))
        lines.append('Author: %s <%s> (%s)' % (self.author, self.email, self.url))
        lines.append('Date: %s' % self.date)
        lines.append('IP: %s' % self.ip)
        lines.append('UserID: %d ParentID: %d' % (self.user, self.parent))
        lines.append('Content:')
        lines.append(self.content and self.content or '')
        return '\n'.join(lines)

    def print (self):
        print(self.stringify())
        return 0


#----------------------------------------------------------------------
# CommentManager
#----------------------------------------------------------------------
class CommentManager (object):

    def __init__ (self):
        self.comments = {}
        self.posts = {}

    def reset (self):
        self.comments = {}
        self.posts = {}

    def append (self, comment):
        if comment.uuid not in self.posts:
            self.posts[comment.uuid] = []
        self.comments[comment.cid] = comment
        self.posts[comment.uuid].append(comment)

    def __getitem__ (self, key):
        return self.comments[key]

    def __contains__ (self, key):
        return key in self.comments

    def __len__ (self):
        return len(self.comments)

    def __iter__ (self):
        return self.comments.__iter__()

    def save (self, fn):
        arr = []
        for cid in self.comments:
            comment = self.comments[cid]
            arr.append(comment.to_dict())
        asclib.state.save_json(fn, arr)
        return 0

    def load (self, fn):
        self.reset()
        if not os.path.exists(fn):
            raise IOError('file not found: %s' % fn)
        arr = asclib.state.load_json(fn)
        for obj in arr:
            comment = Comment(0,0,'','','','','')
            comment.from_dict(obj)
            self.append(comment)
        return 0

    def load_from_xml (self, fn):
        content = asclib.posix.load_file_text(fn)
        soup = bs4.BeautifulSoup(content, 'lxml-xml')
        items = soup.find_all('item')
        comments = []
        for item in items:
            title = item.title.string
            link = item.link.string
            post_id = item.find('wp:post_id').string
            uuid = int(post_id)
            wpcomments = item.find_all('wp:comment')
            for wpcomment in wpcomments:
                wptype = wpcomment.find('wp:comment_type').string
                if wptype != 'pingback' and wptype != 'trackback':
                    self.__extract_wp_comment(uuid, wpcomment)
        return 0

    def __extract_wp_comment (self, uuid, wpcomment):
        cid = int(wpcomment.find('wp:comment_id').string)
        author = wpcomment.find('wp:comment_author').string
        email = wpcomment.find('wp:comment_author_email').string
        url = wpcomment.find('wp:comment_author_url').string
        ip = wpcomment.find('wp:comment_author_IP').string
        date = wpcomment.find('wp:comment_date').string
        content = wpcomment.find('wp:comment_content').string
        user = int(wpcomment.find('wp:comment_user_id').string)
        parent = int(wpcomment.find('wp:comment_parent').string)
        comment = Comment(uuid, cid, author, email, url, ip, date, content, user, parent)
        self.append(comment)
        return comment


#----------------------------------------------------------------------
# ArchiveWebsite
#----------------------------------------------------------------------
class ArchiveWebsite (object):

    def __init__ (self, location):
        self.root = os.path.abspath(location)
        self.index = {}

    def __len__ (self):
        return len(self.index)

    def __getitem__ (self, key):
        return self.index[key]

    def __iter__ (self):
        return self.index.__iter__()
    
    def path (self, *args):
        return os.path.abspath(os.path.join(self.root, *args))

    def load_index (self):
        fn = self.path('index.json')
        db = asclib.state.load_json(fn)
        output = []
        self.index = {}
        for index in db:
            urls = index['urls']
            obj = None
            for key in urls:
                if obj is None:
                    obj = urls[key]
                else:
                    raise Exception('multiple url object found')
            url = obj['url']
            if '/blog/archives/' not in url:
                continue
            if '/blog/wp-json/oembed/1.0' in url:
                continue
            if '/blog/archives/date/' in url:
                continue
            if '/blog/archives/author/' in url:
                continue
            if '?' in url:
                continue
            if 'feed' in url:
                continue
            item = {}
            item['url'] = url
            item['filename'] = self.path(obj['folder'], obj['filename'])
            item['mimetype'] = obj['mimetype']
            item['orignal'] = obj['url_original']
            item['filetime'] = obj['filetime']
            pos = url.rfind('/')
            if pos < 0:
                raise('Bad url')
            slug = url[pos + 1:]
            uuid = int(slug)
            item['uuid'] = uuid
            output.append((uuid, item))
        output.sort()
        for uuid, item in output:
            self.index[uuid] = item
        return 0

    def load_post (self, uuid):
        if uuid not in self.index:
            return None
        item = self.index[uuid]
        fn = item['filename']
        content = asclib.posix.load_file_text(fn)
        soup = bs4.BeautifulSoup(content, 'lxml')
        return soup

    def extract_post (self, uuid):
        soup = self.load_post(uuid)
        if soup is None:
            return None
        comments = soup.find('div', id = 'comments')
        ol = comments.find('ol')
        if ol is None:
            return None
        commentlist = ol.find_all('li', recursive = False)
        output = []
        for li in commentlist:
            if 'class' in li.attrs:
                classes = li['class']
                if 'comment' not in classes:
                    continue
            if 'id' not in li.attrs:
                print('fuck', li)
            commentid = li['id']
            pos = commentid.rfind('-')
            if pos < 0:
                raise Exception('bad commentid')
            cid = int(commentid[pos + 1:])
            comment = self.extract_comment(uuid, cid, li)
            output.append(comment)
        return output

    def __extract_author (self, comment: Comment, div: bs4.element.Tag):
        img: bs4.element.Tag = div.find('img')
        if img:
            if 'class' in img.attrs:
                if 'avatar' in img['class']:
                    comment.avatar = img.src
        cite: bs4.element.Tag = div.find('cite')
        if cite:
            comment.author = cite.string
            a: bs4.element.Tag = cite.find('a')
            if a:
                url = a['href']
                comment.url = url
        return 0

    def __extract_meta (self, comment: Comment, div: bs4.element.Tag):
        a: bs4.element.Tag = div.find('a')
        if not a:
            return 0
        text = a.string
        if 'at' in text:
            text = text.replace('at ', '').replace('/', '-')
        comment.date = text
        return 0

    def __extract_body (self, comment: Comment, div: bs4.element.Tag):
        comment.content = div.decode_contents()
        return 0

    def __extract_legacy_author (self, comment: Comment, div: bs4.element.Tag):
        img: bs4.element.Tag = div.find('img')
        if img:
            if 'class' in img.attrs:
                if 'avatar' in img['class']:
                    comment.avatar = img.src
        tag = div.find('div', class_ = 'name')
        a = tag.find('a')
        if not a:
            name = tag.get_text()
            comment.author = name.strip()
            if comment.author == 'skywind':
                comment.user = 1
        else:
            name = a.get_text()
            comment.author = name.strip()
            url = a['href']
            comment.url = url
            if url == '/blog':
                comment.user = 1
        return 0

    def __extract_legacy_info (self, comment: Comment, div: bs4.element.Tag):
        tag = div.find('div', class_ = 'date')
        if tag:
            text = tag.get_text().strip()
            text, _, _ = text.partition('|')
            text = text.strip()
            text = self.__convert_date(text)
            comment.date = text
        tag: bs4.element.Tag = div.find('div', class_ = 'content')
        if tag:
            content = tag.div.decode_contents()
            comment.content = content
        return 0

    def __convert_date (self, text):
        if 'at' not in text:
            return text
        text = text.replace('at ', '').replace(',', '')
        pos = text.find(' ')
        if pos >= 0:
            p1 = text[:pos]
            p2 = text[pos + 1:]
            p2 = p2.replace('st', '').replace('nd', '')
            p2 = p2.replace('rd', '').replace('th', '')
            text = p1 + ' ' + p2
        parsed_date = datetime.datetime.strptime(text, "%B %d %Y %H:%M")
        formatted_date = parsed_date.strftime("%Y-%m-%d %H:%M")
        return formatted_date

    def extract_comment (self, uuid, cid, tag: bs4.element.Tag):
        comment = Comment(uuid, cid, '', '', '', '', '')
        if 'class' in tag.attrs:
            classes = tag['class']
            if 'bypostauthor' in classes:
                comment.user = 1
        version = 0
        if tag.find('div', class_ = 'author'):
            version = 1
        if version == 0:
            for div in tag.div.find_all('div'):
                if 'class' not in div.attrs:
                    continue
                classes = div['class']
                if 'comment-author' in classes:
                    self.__extract_author(comment, div)
                elif 'comment-meta' in classes:
                    self.__extract_meta(comment, div)
                elif 'comment-body' in classes:
                    self.__extract_body(comment, div)
        else:
            for div in tag.find_all('div'):
                if 'class' not in div.attrs:
                    continue
                classes = div['class']
                # print('suck1', classes)
                if 'author' in classes:
                    self.__extract_legacy_author(comment, div)
                elif 'info' in classes:
                    self.__extract_legacy_info(comment, div)
        return comment


#----------------------------------------------------------------------
# tables
#----------------------------------------------------------------------
TABLE_STRUCTURE = (
    "comment_ID",
    "comment_post_ID",
    "comment_author",
    "comment_author_email",
    "comment_author_url",
    "comment_author_IP",
    "comment_date",
    "comment_date_gmt",
    "comment_content",
    "comment_karma",
    "comment_approved",
    "comment_agent",
    "comment_type",
    "comment_parent",
    "user_id"
    )

TABLE_ROWS = {i: key for i, key in enumerate(TABLE_STRUCTURE)}


#----------------------------------------------------------------------
# gmt time conversion
#----------------------------------------------------------------------
def gmt_time_conversion(date_str):
    # print(f'converting time: "{date_str}"')
    if len(date_str) == 16:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    elif len(date_str) == 19:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    else:
        return date_str
    d2 = dt - datetime.timedelta(hours = 8)
    gmt_date_str = d2.strftime("%Y-%m-%d %H:%M:%S")
    return gmt_date_str


#----------------------------------------------------------------------
# comment to row
#----------------------------------------------------------------------
def comment_to_row(comment: Comment):
    row = [''] * len(TABLE_STRUCTURE)
    row[0] = str(comment.cid)
    row[1] = str(comment.uuid)
    row[2] = comment.author
    row[3] = comment.email and comment.email or ''
    row[4] = comment.url and comment.url or ''
    row[5] = comment.ip and comment.ip or ''
    row[6] = comment.date and comment.date or ''
    row[7] = gmt_time_conversion(comment.date)
    row[8] = comment.content
    row[9] = '0'
    row[10] = 1
    row[11] = ''
    row[12] = ''
    row[13] = str(comment.parent)
    row[14] = str(comment.user)
    return row


#----------------------------------------------------------------------
# 
#----------------------------------------------------------------------
def export_comments_to_csv(cm: CommentManager, filename: str):
    import csv
    with open(filename, 'w', encoding = 'utf-8', newline = '') as f:
        writer = csv.writer(f)
        writer.writerow(TABLE_STRUCTURE)
        for cid in cm:
            comment = cm[cid]
            row = comment_to_row(comment)
            writer.writerow(row)
    return 0


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
    def test2():
        cm = CommentManager()
        cm.load_from_xml(location('skywindinside.xml'))
        print(len(cm))
        cm.save(location('skywindinside.json'))
        cm.load(location('skywindinside.json'))
        print(len(cm))
        return 0
    def test3():
        aw = ArchiveWebsite(location('website'))
        aw.load_index()
        LOCATE = 'E:/Site/recover/'
        print(aw[120]['filename'])
        print(aw[66]['filename'])
        comments = aw.extract_post(120)
        for comment in comments:
            comment.print()
            print('-----')
    def test4():
        aw = ArchiveWebsite(location('website'))
        cm = CommentManager()
        aw.load_index()
        # print(comments)
        for uuid in aw:
            print(aw[uuid]['url'])
            comments = aw.extract_post(uuid)
            if comments is None:
                print('skip')
                continue
            for comment in comments:
                cm.append(comment)
            print('extracted %d comments' % len(comments))
        cm.save(location('latest_comments.json'))
        return 0
    def test5():
        cm = CommentManager()
        cm.load(location('latest_comments.json'))
        print('total comments:', len(cm))
        for cid in cm:
            comment = cm[cid]
            if not comment.content:
                print('empty comment:', comment.cid, comment.author)
            if not comment.author:
                print('anonymous comment:', comment.cid, comment.content)
        return 0
    def test6():
        cm1 = CommentManager()
        cm2 = CommentManager()
        cm1.load(location('skywindinside.json'))
        cm2.load(location('comment_website.json'))
        count0 = len(cm1)
        count1 = 0
        count2 = 0
        for cid in cm1:
            comment: Comment = cm1[cid]
            comment.origin = 'export'
        for cid in cm2:
            comment: Comment = cm2[cid]
            comment.origin = 'website'
            if comment.uuid == 3:
                comment.uuid = 41
            if cid not in cm1:
                cm1.append(comment)
                count1 += 1
            else:
                count2 += 1
        print('original comments:', count0)
        print('new comments:', count1)
        print('duplicate comments:', count2)
        print('total comments:', len(cm1))
        for cid in cm1:
            comment = cm1[cid]
            if comment.uuid == 3:
                comment.uuid = 41
            if comment.url == 'http://www.skywind.me/blog':
                comment.url = '/blog'
            elif comment.url == 'http://skywind.me/blog':
                comment.url = '/blog'
            elif comment.url == 'http://www.joynb.net/blog':
                comment.url = '/blog'
        cm1.save(location('skywind_comments.json'))
        return 0
    def test7():
        print(gmt_time_conversion('2025-10-18 06:30'))
        cm = CommentManager()
        cm.load(location('skywind_comments.json'))
        print(len(cm))
        export_comments_to_csv(cm, location('skywind_comments.csv'))
        return 0
    test6()


