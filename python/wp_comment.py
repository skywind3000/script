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
import bs4.element
import cinit
import asclib
import asclib.posix
import asclib.core
import asclib.state
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
        self.reference = ''

    def __repr__ (self):
        return '<Comment %d:%d %s>' % (self.uuid, self.cid, self.author)

    def to_dict (self):
        return {
            'uuid': self.uuid,
            'cid': self.cid,
            'author': self.author,
            'email': self.email,
            'url': self.url,
            'ip': self.ip,
            'date': self.date,
            'content': self.content,
            'user': self.user,
            'parent': self.parent,
            'reference': self.reference,
        }

    def from_dict (self, obj):
        self.uuid = obj['uuid']
        self.cid = obj['cid']
        self.author = obj['author']
        self.email = obj['email']
        self.url = obj['url']
        self.ip = obj['ip']
        self.date = obj['date']
        self.content = obj['content']
        self.user = obj['user']
        self.parent = obj['parent']
        self.reference = obj['reference']
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
        return 0

    def __extract_meta (self, comment: Comment, div: bs4.element.Tag):
        return 0

    def __extract_body (self, comment: Comment, div: bs4.element.Tag):
        p: bs4.element.Tag = div.find('p')
        if p is not None:
            comment.content = p.decode_contents()
        else:
            comment.content = div.decode_contents()
        return 0

    def extract_comment (self, uuid, cid, tag: bs4.element.Tag):
        comment = Comment(uuid, cid, '', '', '', '', '')
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
        comment.print()
        print()
        return comment



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
        print(aw[131]['filename'])
        comments = aw.extract_post(131)
        # comments = aw.extract_post(83)
        # print(comments)
        if 0:
            for uuid in aw:
                print(aw[uuid]['url'])
                aw.extract_post(uuid)
        return 0
    test3()


