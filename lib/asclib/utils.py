#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# utils.py - 
#
# Created by skywind on 2024/12/26
# Last Modified: 2024/12/26 16:57:25
#
#======================================================================
from __future__ import print_function, unicode_literals
import sys
import time
import os
import logging
import logging.handlers


#----------------------------------------------------------------------
# usage: logger = rotate_log('rotate.log')
#----------------------------------------------------------------------
def rotate_log(filename = None, name = None):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter('[%(asctime)s] %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S')

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    def namer(default_name):
        base_filename, ext = os.path.splitext(default_name)
        date_str = base_filename.split('.')[-1]
        try:
            time_tuple = time.strptime(date_str, "%Y-%m-%d")
            name, _ = os.path.splitext(filename)
            return f"{name}.{time.strftime('%Y%m%d', time_tuple)}{ext}"
        except:
            return default_name

    if filename:
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=filename, when='midnight', interval=1,    
            backupCount=7, encoding='utf-8')
        file_handler.namer = namer
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


