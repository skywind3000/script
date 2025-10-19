#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# cinit.py - 
#
# Created by skywind on 2024/09/12
# Last Modified: 2024/09/12 10:37:40
#
#======================================================================
import sys
import os
import site

DIRNAME = os.path.dirname(os.path.abspath(__file__))
site.addsitedir(os.path.normpath(os.path.join(DIRNAME, '../lib')))


# completion hint
if 0:
    sys.path.append('../lib')
    sys.path.append('../../vim/lib')
    sys.path.append('C:/Share/script/lib')


# pylint: disable-next=wrong-import-position
import ascmini   # noqa: E402

# pylint: disable-next=wrong-import-position
import asclib    # noqa: E402
import asclib.posix
import asclib.core

