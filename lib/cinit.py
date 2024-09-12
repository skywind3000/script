#! /usr/bin/env python
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

DIRNAME = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.normpath(os.path.join(DIRNAME, '../../vim/lib')))

# pylint: disable-next=wrong-import-position
import ascmini   # noqa: E402


