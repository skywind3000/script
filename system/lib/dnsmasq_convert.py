#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# dnsmasq_convert.py - 
#
# Last Modified: 2024/12/11 10:23:26
#
#======================================================================
import sys
import os

if len(sys.argv) < 3:
    print('usage: %s {filename} {server} [ipset]'%sys.argv[0])
    sys.exit(1)

filename = sys.argv[1].strip('\r\n\t ')
server = sys.argv[2].strip('\r\n\t ')
ipset = (len(sys.argv) >= 4) and sys.argv[3].strip('\r\n\t ') or ''

if not filename:
    print('invalid filename')
    sys.exit(1)

if not server:
    print('invalid server')
    sys.exit(1)

if not os.path.exists(filename):
    print('read file error: %s'%filename)
    sys.exit(1)

for line in open(filename):
    line = line.strip('\r\n\t ')
    if not line:
        continue
    if line.startswith('#'):
        continue
    print('server=/%s/%s'%(line, server))
    if ipset:
        print('ipset=/%s/%s'%(line, ipset))
    print('')


