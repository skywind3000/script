#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# string.py - 
#
# Created by skywind on 2025/10/21
# Last Modified: 2025/10/21 20:54:02
#
#======================================================================
from __future__ import print_function, unicode_literals
import sys


#----------------------------------------------------------------------
# count_substring(haystack, needle) -> int
#----------------------------------------------------------------------
def count_substring(haystack, needle):
    count = 0
    start = 0
    while True:
        start = haystack.find(needle, start)
        if start == -1:
            break
        count += 1
        start += len(needle)
    return count


#----------------------------------------------------------------------
# text to html
#----------------------------------------------------------------------
def text_to_html(text: str) -> str:
    html = text.replace('&', '&amp;')
    html = html.replace('<', '&lt;')
    html = html.replace('>', '&gt;')
    html = html.replace('\n', '<br>\n')
    return html


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        s = "ababcabcabc"
        n = "abc"
        c = count_substring(s, n)
        print(f"count_substring('{s}', '{n}') = {c}")  #
        return 0
    test1()

