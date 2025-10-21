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
import cinit
import asclib
import wp_comment

from wp_comment import Comment, CommentManager
from wp_comment import location


#----------------------------------------------------------------------
# 
#----------------------------------------------------------------------
def analyse_comments(filename):
    return 0


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        analyse_comments(location('comment_primitive.json'))
        return 0
    test1()

