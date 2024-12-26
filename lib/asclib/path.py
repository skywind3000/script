#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# path.py - 
#
# Created by skywind on 2024/12/26
# Last Modified: 2024/12/26 11:19:44
#
#======================================================================
from __future__ import print_function, unicode_literals
import sys
import os
import shutil

try:
    from . import core
except ImportError:
    import core

UNIX = core.UNIX


#----------------------------------------------------------------------
# absolute path
#----------------------------------------------------------------------
def abspath(path, unixsep = False, resolve = False):
    if path is None:
        return None
    if '~' in path:
        path = os.path.expanduser(path)
    path = os.path.abspath(path)
    if (not UNIX) and unixsep:
        return path.lower().replace('\\', '/')
    if resolve:
        return os.path.abspath(os.path.realpath(path))
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
# copy file tree
#----------------------------------------------------------------------
def xcopytree(src, dst, override = False):
    import shutil
    if not os.path.exists(src):
        return -1
    if os.path.exists(dst) and (not override):
        for root, dirs, files in os.walk(src):
            for file in files:
                srcname = os.path.join(root, file)
                relname = os.path.relpath(root, src)
                dstname = os.path.join(dst, relname, file)
                if not os.path.exists(dstname):
                    dirname = os.path.dirname(dstname)
                    if not os.path.exists(dirname):
                        os.makedirs(dirname, exist_ok = True)
                    shutil.copy2(srcname, dstname)
    else:
        os.makedirs(dst, exist_ok = True)
        shutil.copytree(src, dst, dirs_exist_ok = True)
    return 0


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
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        print(which('gcc'))
        return 0
    test1()


