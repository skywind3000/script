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
except ImportError:
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
# ensure path exists
#----------------------------------------------------------------------
def ensure_path(path):
    if not path:
        return False
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except:
            return False
    return True


#----------------------------------------------------------------------
# get standard path 
#----------------------------------------------------------------------
def __stdpath(name):
    if not name:
        name = 'temp'
    if name == 'temp':
        if UNIX:
            return os.path.normpath('/tmp')
        else:
            t = os.environ.get('TEMP', 'C:/Temp')
            return os.path.normpath(t)
    if name in ('home', 'user', '~'):
        return os.path.expanduser('~')
    if name == 'config':
        if 'XDG_CONFIG_HOME' in os.environ:
            return os.path.normpath(os.environ['XDG_CONFIG_HOME'])
        return os.path.normpath(os.path.expanduser('~/.config'))
    if name == 'data':
        if 'XDG_DATA_HOME' in os.environ:
            return os.path.normpath(os.environ['XDG_DATA_HOME'])
        return os.path.normpath(os.path.expanduser('~/.local/share'))
    if name == 'cache':
        if 'XDG_CACHE_HOME' in os.environ:
            return os.path.normpath(os.environ['XDG_CACHE_HOME'])
        return os.path.normpath(os.path.expanduser('~/.cache'))
    if name == 'desktop':
        if 'XDG_DESKTOP_DIR' in os.environ:
            return os.path.normpath(os.environ['XDG_DESKTOP_DIR'])
        return os.path.normpath(os.path.expanduser('~/Desktop'))
    return None


#----------------------------------------------------------------------
# get standard path
#----------------------------------------------------------------------
def stdpath(name):
    path = __stdpath(name)
    ensure_path(path)
    return path


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
# replace file atomicly
#----------------------------------------------------------------------
def replace_file(srcname, dstname):
    if sys.platform[:3] != 'win':
        try:
            os.rename(srcname, dstname)
        except OSError:
            return False
    else:
        import ctypes.wintypes
        kernel32 = ctypes.windll.kernel32
        wp, vp, cp = ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_char_p
        DWORD, BOOL = ctypes.wintypes.DWORD, ctypes.wintypes.BOOL
        kernel32.ReplaceFileA.argtypes = [ cp, cp, cp, DWORD, vp, vp ]
        kernel32.ReplaceFileW.argtypes = [ wp, wp, wp, DWORD, vp, vp ]
        kernel32.ReplaceFileA.restype = BOOL
        kernel32.ReplaceFileW.restype = BOOL
        kernel32.GetLastError.argtypes = []
        kernel32.GetLastError.restype = DWORD
        success = False
        try:
            os.rename(srcname, dstname)
            return True
        except OSError:
            pass
        if sys.version_info[0] < 3 and isinstance(srcname, str):
            hr = kernel32.ReplaceFileA(dstname, srcname, None, 2, None, None)
        else:
            hr = kernel32.ReplaceFileW(dstname, srcname, None, 2, None, None)
        if not hr:
            return False
    return True


#----------------------------------------------------------------------
# random temp 
#----------------------------------------------------------------------
def tmpname(filename, fill = 5):
    import time, os, random
    while 1:
        name = '.' + str(int(time.time() * 1000000))
        for i in range(fill):
            k = random.randint(0, 51)
            name += (k < 26) and chr(ord('A') + k) or chr(ord('a') + k - 26)
        test = filename + name + str(os.getpid())
        if not os.path.exists(test):
            return test
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
# save file atomicly
#----------------------------------------------------------------------
def save_file_content_atomic(filename, content, mode = 'w'):
    tmp = tmpname(filename)
    if not tmp:
        return False
    if not save_file_content(tmp, content, mode):
        return False
    if not replace_file(tmp, filename):
        return False
    return True


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
    if isinstance(content, bytes):
        return save_file_content(filename, content)
    with codecs.open(filename, 'w', 
            encoding = encoding, 
            errors = 'ignore') as fp:
        fp.write(content)
    return True


#----------------------------------------------------------------------
# save file text atomicly
#----------------------------------------------------------------------
def save_file_text_atomic(filename, content, encoding = None):
    if encoding is None:
        encoding = 'utf-8'
    if isinstance(content, bytes):
        return save_file_content_atomic(filename, content)
    tmp = tmpname(filename)
    if not tmp:
        return False
    with codecs.open(tmp, 'w', 
            encoding = encoding, 
            errors = 'ignore') as fp:
        fp.write(content)
    if not replace_file(tmp, filename):
        return False
    return True


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        content = load_file_content(__file__)
        print(content)
        print(which('gcc2'))
        return 0
    test1()



