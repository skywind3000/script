#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# errno_to_string.py - 
#
# Last Modified: 2025/01/02 14:56:22
#
# NOTE: 
# 
# alternative: errno command in 'moreutils' (apt install moreutils)
#
#======================================================================
import sys
import os
import errno

def errno_to_string(errno_value):
    """Convert errno value to human-readable string."""
    return os.strerror(errno_value)

if len(sys.argv) < 2:
    print('usage: %s {errno}' % sys.argv[0])
    sys.exit(1)

num = int(sys.argv[1])

print('%d: %s' % (num, errno_to_string(num)))

