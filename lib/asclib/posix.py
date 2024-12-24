#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# posix.py - 
#
# Created by skywind on 2024/12/24
# Last Modified: 2024/12/24 13:49:10
#
#======================================================================
from __future__ import print_function, unicode_literals
import sys
import os
import codecs

try:
    from . import core
except:
    import core

UNIX = core.UNIX


#----------------------------------------------------------------------
# mkdir recursive
#----------------------------------------------------------------------
def mkdir(path):
    unix = sys.platform[:3] != 'win' and True or False
    path = os.path.abspath(path)
    if os.path.exists(path):
        return False
    name = ''
    part = os.path.abspath(path).replace('\\', '/').split('/')
    if unix:
        name = '/'
    if (not unix) and (path[1:2] == ':'):
        part[0] += '/'
    for n in part:
        name = os.path.abspath(os.path.join(name, n))
        if not os.path.exists(name):
            os.mkdir(name)
    return True


#----------------------------------------------------------------------
# remove tree
#----------------------------------------------------------------------
def rmtree(path, ignore_error = False, onerror = None):
    import shutil
    shutil.rmtree(path, ignore_error, onerror)
    return True


#----------------------------------------------------------------------
# absolute path
#----------------------------------------------------------------------
def abspath(path, resolve = False):
    if path is None:
        return None
    if '~' in path:
        path = os.path.expanduser(path)
    path = os.path.abspath(path)
    if not UNIX:
        return path.lower().replace('\\', '/')
    if resolve:
        return os.path.abspath(os.path.realpath(path))
    return path


#----------------------------------------------------------------------
# which file
#----------------------------------------------------------------------
def which(name, prefix = None, postfix = None):
    if not prefix:
        prefix = []
    if not postfix:
        postfix = []
    PATH = os.environ.get('PATH', '').split(UNIX and ':' or ';')
    search = prefix + PATH + postfix
    for path in search:
        fullname = os.path.join(path, name)
        if os.path.exists(fullname):
            return fullname
    return None


#----------------------------------------------------------------------
# load content
#----------------------------------------------------------------------
def load_file_content(filename, mode = 'r'):
    if hasattr(filename, 'read'):
        try: content = filename.read()
        except: content = None
        return content
    try:
        if '~' in filename:
            filename = os.path.expanduser(filename)
        fp = open(filename, mode)
        content = fp.read()
        fp.close()
    except:
        content = None
    return content


#----------------------------------------------------------------------
# save file content
#----------------------------------------------------------------------
def save_file_content(filename, content, mode = 'w'):
    try:
        fp = open(filename, mode)
        fp.write(content)
        fp.close()
    except:
        return False
    return True


#----------------------------------------------------------------------
# auto detect encoding and decode into a string
#----------------------------------------------------------------------
def string_auto_decode(payload, encoding = None):
    content = None
    if payload is None:
        return None
    if hasattr(payload, 'read'):
        try: content = payload.read()
        except: pass
    else:
        content = payload
    if sys.version_info[0] >= 3:
        if isinstance(content, str):
            return content
    else:
        # pylint: disable-next=else-if-used
        if isinstance(content, unicode):   # noqa
            return content
    if content is None:
        return None
    if not isinstance(payload, bytes):
        return str(payload)
    if content[:3] == b'\xef\xbb\xbf':
        return content[3:].decode('utf-8', 'ignore')
    elif encoding is not None:
        return content.decode(encoding, 'ignore')
    guess = [sys.getdefaultencoding(), 'utf-8']
    if sys.stdout and sys.stdout.encoding:
        guess.append(sys.stdout.encoding)
    try:
        import locale
        guess.append(locale.getpreferredencoding())
    except:
        pass
    visit = {}
    text = None
    for name in guess + ['gbk', 'ascii', 'latin1']:
        if name in visit:
            continue
        visit[name] = 1
        try:
            text = content.decode(name)
            break
        except:
            pass
    if text is None:
        text = content.decode('utf-8', 'ignore')
    return text



#----------------------------------------------------------------------
# load file and guess encoding
#----------------------------------------------------------------------
def load_file_text(filename, encoding = None):
    content = load_file_content(filename, 'rb')
    if content is None:
        return None
    return string_auto_decode(content, encoding)


#----------------------------------------------------------------------
# save file text
#----------------------------------------------------------------------
def save_file_text(filename, content, encoding = None):
    if encoding is None:
        encoding = 'utf-8'
    if (not isinstance(content, unicode)) and isinstance(content, bytes):
        return save_file_content(filename, content)
    with codecs.open(filename, 'w', 
            encoding = encoding, 
            errors = 'ignore') as fp:
        fp.write(content)
    return True


#----------------------------------------------------------------------
# check file is in directory
#----------------------------------------------------------------------
def in_directory(filename, directory):
    root = os.path.normcase(os.path.abspath(directory))
    name = os.path.normcase(os.path.abspath(filename))
    if not root.endswith(os.path.sep):
        if (not root.endswith('/')) and (not root.endswith('\\')):
            root = os.path.normcase(root + os.path.sep)
    return name.startswith(root)


#----------------------------------------------------------------------
# find file recursive
#----------------------------------------------------------------------
def find_files(root, pattern = '*', recursive = True, mode = 0):
    import fnmatch
    matched = []
    root = os.path.normpath(os.path.abspath(root))
    names = None   # noqa
    if not recursive:
        for fn in fnmatch.filter(os.listdir(root), pattern):
            path = os.path.join(root, fn)
            if (mode & 3) == 0:
                matched.append(path)
            else:
                # pylint: disable-next=else-if-used
                if os.path.isdir(path):
                    if (mode & 1) == 0:
                        matched.append(path)
                else:
                    # pylint: disable-next=else-if-used
                    if (mode & 2) == 0:
                        matched.append(path)
    else:
        for base, dirnames, filenames in os.walk(root):
            if (mode & 1) == 0:
                for dirname in fnmatch.filter(dirnames, pattern):
                    matched.append(os.path.join(base, dirname))
            if (mode & 2) == 0:
                for filename in fnmatch.filter(filenames, pattern):
                    matched.append(os.path.join(base, filename))
    if (mode & 4) != 0:
        selected = []
        prefix = os.path.normcase(root)
        if not prefix.endswith(os.path.sep):
            if (not prefix.endswith('/')) and (not prefix.endswith('\\')):
                prefix = os.path.normcase(root + os.path.sep)
        for path in matched:
            t = os.path.normcase(path)
            if t.startswith(prefix):
                selected.append(path[len(prefix):])
        matched = selected
    return matched


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        content = load_file_content(__file__)
        print(content)
        print(which('gcc'))
        return 0
    test1()



