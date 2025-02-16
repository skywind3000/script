#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# bwmon2.py - Bandwidth Monitor
#
# Last Modified: 2025/02/16 17:15:39
#
#======================================================================
import sys
import os
import re
import loguru


#----------------------------------------------------------------------
# popen_shell
#----------------------------------------------------------------------
def popen_shell(cmdline):
    import subprocess
    p = subprocess.Popen(cmdline, shell = True,
                         stdin = subprocess.PIPE, 
                         stdout = subprocess.PIPE,
                         stderr = subprocess.STDOUT)
    stdin, stdouterr = (p.stdin, p.stdout)
    stdin.close()
    content = stdouterr.read()
    stdouterr.close()
    if p: p.wait()
    code = -1
    if 'returncode' in p.__dict__:
        code = int(p.returncode)
    if isinstance(content, bytes):
        text = content.decode('utf-8', 'ignore')
    else:
        text = content
    return code, text


#----------------------------------------------------------------------
# iftop_parse
#----------------------------------------------------------------------
def iftop_parse(content):
    if isinstance(content, bytes):
        cc = content.decode('utf-8', 'ignore')
    elif isinstance(content, str):
        cc = content
    else:
        c1 = content.read()
        if isinstance(c1, str):
            cc = c1
        elif isinstance(c1, bytes):
            cc = c1.decode('utf-8', 'ignore')
        else:
            raise TypeError('type mismatch: %s'%type(content))
    items = []
    previous = ''
    for line in cc.split('\n'):
        line = line.strip('\r\n\t ')
        if not line:
            continue 
        if ('=>' not in line) and ('<=' not in line):
            continue
        if '<=' in line:
            part1 = previous.split()
            part2 = line.split()
            if len(part1) >= 7 or len(part2) >= 6:
                item = {}
                item['dst'] = part1[1].strip()
                item['src'] = part2[0].strip()
                item['down_2s'] = part1[3]
                item['down_10s'] = part1[4]
                item['down_40s'] = part1[5]
                item['down_acc'] = part1[6]
                item['up_2s'] = part2[2]
                item['up_10s'] = part2[3]
                item['up_40s'] = part2[4]
                item['up_acc'] = part2[5]
                items.append(item)
        previous = line
    output = []
    scale = {'Kb': 1024.0, 'KB': 8192.0}
    scale['Mb'] = 1024.0 * 1024
    scale['MB'] = 1024.0 * 8192
    scale['Gb'] = 1024.0 * 1024 * 1024
    scale['GB'] = 1024.0 * 1024 * 8192
    scale['b'] = 1.0
    scale['B'] = 8.0
    for item in items:
        ni = {}
        ni['src'] = item['src']
        ni['dst'] = item['dst']
        for key in item:
            if key == 'src' or key == 'dst':
                continue
            value = item[key].strip()
            m = re.match(r'([\d.]+)\s*([A-Za-z]+)', value)
            x = float(str(m.group(1)))
            s = str(m.group(2))
            z = x * scale[s]
            ni[key] = z
        ni['tot_2s'] = ni['up_2s'] + ni['down_2s']
        ni['tot_10s'] = ni['up_10s'] + ni['down_10s']
        ni['tot_40s'] = ni['up_40s'] + ni['down_40s']
        ni['tot_acc'] = ni['up_acc'] + ni['down_acc']
        output.append(ni)
    return output


#----------------------------------------------------------------------
# iftop_finalize
#----------------------------------------------------------------------
def iftop_finalize(content):
    host = {}
    for item in iftop_parse(content):
        ip = item['src']
        ni = {}
        ni['up_rate'] = item['up_10s']
        ni['up_acc'] = item['up_acc']
        ni['down_rate'] = item['down_10s']
        ni['down_acc'] = item['down_acc']
        ni['total_rate'] = ni['up_rate'] + ni['down_rate']
        ni['total_acc'] = ni['up_acc'] + ni['down_acc']
        if ip not in host:
            host[ip] = {}
        current = host[ip]
        for key in ni:
            if key not in current:
                current[key] = 0.0
            current[key] += ni[key]
        host[ip] = current
    output = []
    for ip in host:
        item = host[ip]
        ni = {'ip': ip}
        for key in item:
            ni[key] = item[key]
        output.append(ni)
    output.sort(key = lambda x: x['total_rate'], reverse = True)
    return output


#----------------------------------------------------------------------
# arp-scan -I eth2 --localnet --format='...' --resolv
#----------------------------------------------------------------------
def arp_scan(content):
    if isinstance(content, bytes):
        cc = content.decode('utf-8', 'ignore')
    elif isinstance(content, str):
        cc = content
    else:
        c1 = content.read()
        if isinstance(c1, str):
            cc = c1
        elif isinstance(c1, bytes):
            cc = c1.decode('utf-8', 'ignore')
        else:
            raise TypeError('type mismatch: %s'%type(content))
    host = {}
    for line in cc.split('\n'):
        line = line.strip('\r\n\t ')
        if not line:
            continue
        if '\t' not in line:
            continue
        part = line.split('\t')
        if len(part) < 3:
            continue
        ni = {}
        ip = part[0].strip()
        ni['ip'] = ip
        ni['mac'] = part[1].strip()
        ni['name'] = part[2].strip()
        ni['vendor'] = ''
        if len(part) > 3:
            ni['vendor'] = part[3]
        host[ip] = ni
    return host


#----------------------------------------------------------------------
# iftop_log
#----------------------------------------------------------------------
def iftop_log(content, arpscan, logger):
    output = iftop_finalize(content)
    arps = arp_scan(arpscan)
    for item in output:
        ip = item['ip']
        part = ['ip=%s'%ip]
        if ip in arps:
            info = arps[ip]
            part.append('mac=%s'%info['mac'])
            name = info['name']
            if name != ip:
                part.append('name=%s'%name)
            else:
                part.append('name=%s'%info['vendor'])
        scale = 1024.0 * 1024
        scale = 1024.0
        up = item['up_rate'] / scale
        down = item['down_rate'] / scale
        total = item['total_rate'] / scale
        part.append('up=%.2f'%up)
        part.append('down=%.02f'%down)
        part.append('total=%.02f'%total)
        part = [n.replace('`', '.') for n in part]
        text = '`'.join(part)
        logger.info('info: ' + text)
    return 0


#----------------------------------------------------------------------
# init log
#----------------------------------------------------------------------
def init_log(logname = None):
    import loguru
    format = "[{time:YYYY-MM-DD HH:mm:ss}] {level} {message}"
    format = "[{time:YYYY-MM-DD HH:mm:ss}] {message}"
    logger = loguru.logger
    logger.remove()
    logger.add(sys.stdout, format=format)
    if logname:
        logger.add(logname, rotation="00:00", retention="1 week", 
                   format=format, level="INFO")
    return logger


#----------------------------------------------------------------------
# main
#----------------------------------------------------------------------
def main(argv = None):
    argv = argv and argv or sys.argv
    argv = [n for n in argv]
    args = argv[1:]
    if len(args) < 1:
        print('usage: %s <interface> [logfile]'%sys.argv[0])
        return 0
    device = argv[1]
    logger = init_log(len(args) >= 2 and args[1] or None)
    logger.info('Starting bandwidth detection ...')
    try:
        fmt = "'${ip}\\t${mac}\\t${name}\\t${vendor}'"
        cmd = 'arp-scan -I %s --localnet --resolve --format=%s'%(device, fmt)
        logger.info('exec: %s'%repr(cmd))
        code, arp = popen_shell(cmd)
        if code != 0:
            logger.error('arp-scan returns %d'%code)
            print(cmd)
            print(arp)
            return 1
        # print(arp_scan(arp))
        cmd = 'iftop -t -s 10 -n -o 10s -L 150 -i %s'%device
        logger.info('exec: %s'%repr(cmd))
        code, iftop = popen_shell(cmd)
        if code != 0:
            logger.error('iftop returns %d'%code)
            logger.error(iftop)
            return 1
        iftop_log(iftop, arp, logger)
        logger.info('finished.')
    except:
        logger.exception("An error occurred")
    return 0


#----------------------------------------------------------------------
# commands
#----------------------------------------------------------------------

# iftop -t -s 10 -n -o 10s -L 200 -i eth2
# arp-scan -I eth2 --localnet --format='${ip}\t${mac}\t${name}\t${vendor}' --resolve


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        logger = loguru.logger
        iftop_log(open('iftop.txt').read(), open('arp.txt').read(), logger)
        return 0
    def test2():
        args = ['', 'eth2']
        main(args)
        return 0
    # test2()
    main()

