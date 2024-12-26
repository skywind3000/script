#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# dler_client.py - 
#
# Created by skywind on 2024/12/23
# Last Modified: 2024/12/23 15:58:34
#
#======================================================================
import sys
import os
import re
import urllib.parse
import base64
import json
import cinit
import ascmini
import asclib.regex
import asclib.path


#----------------------------------------------------------------------
# rules definition
#----------------------------------------------------------------------
url_rules = r'''
    protocol = http|https|trojan|ss
    login_name = [^:@\r\n\t ]+
    login_pass = [^@\r\n\t ]+
    login = {login_name}(:{login_pass})?
    host = [^:/@\r\n\t ]+
    port = \d+
    optional_port = (?:[:]{port})?
    path = [\/\?][^\r\n\t ]*
    url = {protocol}://({login}[@])?{host}{optional_port}{path}?
'''

url_regex = asclib.regex.build(url_rules)


#----------------------------------------------------------------------
# ProxyInfo
#----------------------------------------------------------------------
class ProxyInfo (object):

    def __init__ (self, url):
        self.url = url
        self.mode = None
        self.name = None
        self.host = None
        self.port = 0
        self.password = None
        self.cipher = ''
        self.parse(url)

    def __repr__ (self):
        return 'ProxyInfo(%s)' % repr(self.url)

    def __str__ (self):
        return '<ProxyInfo:%s>' % self.name

    def parse (self, url):
        self.url = url.strip('\r\n\t ')
        if url.startswith('trojan://'):
            self.mode = 'trojan'
        elif url.startswith('ss://'):
            self.mode = 'ss'
        else:
            self.mode = ''
            raise Exception('bad proxy url: %s' % url)
        pattern = url_regex['url']
        s = re.match(pattern, self.url)
        d = s.groupdict()
        self.host = s.group('host').strip('\r\n\t ')
        self.port = d.get('port', '8080')
        self.password = d.get('login', '')
        if self.mode == 'ss':
            t = self.password
            t = base64.b64decode(t).decode('utf-8', 'ignore')
            p1, _, p2 = t.partition(':')
            self.cipher = p1.strip('\r\n\t ')
            self.password = p2.strip('\r\n\t ')
            self.cipher = self.cipher or 'aes-256-cfb'
        path = d.get('path', '')
        path = path.lstrip('/?')
        vars, _, anchor = path.partition('#')
        vars = vars.strip('\r\n\t ')
        anchor = anchor.strip('\r\n\t ')
        self.objs = urllib.parse.parse_qs(vars)
        self.name = urllib.parse.unquote(anchor).strip('\r\n\t ')
        if self.mode == 'ss':
            self.__parse_ss()
        return 0

    def __parse_ss (self):
        objs = self.objs
        plugin = objs.get('plugin', None)
        self.plugin = None
        if plugin:
            info = plugin[0]
            mark = 'obfs-local;'
            if info.startswith(mark):
                self.plugin = {}
                self.plugin['name'] = 'obfs-local'
                self.plugin['opts'] = info[len(mark):].strip('\r\n\t ')
        return 0

    def generate (self):
        if self.mode == 'ss':
            return self.__generate_ss()
        if self.mode == 'trojan':
            return self.__generate_trojan()
        return None

    def __generate_ss (self):
        objs = {}
        objs['server'] = self.host
        objs['server_port'] = int(self.port)
        objs['local_address'] = '{{LOCAL_ADDRESS}}'
        objs['local_port'] = '{{LOCAL_PORT}}'
        objs['password'] = self.password
        objs['method'] = self.cipher
        if self.plugin:
            objs['plugin'] = self.plugin['name']
            objs['plugin_opts'] = self.plugin['opts']
        objs['mode'] = 'tcp_and_udp'
        objs['timeout'] = 60
        objs['fast_open'] = False
        objs['reuse_port'] = True
        text = json.dumps(objs, indent = 4)
        return text

    def __generate_trojan (self):
        objs = {}
        objs['run_type'] = 'client'
        objs['local_addr'] = '{{LOCAL_ADDRESS}}'
        objs['local_port'] = '{{LOCAL_PORT}}'
        objs['remote_addr'] = self.host
        objs['remote_port'] = int(self.port)
        objs['password'] = [self.password]
        objs['log_level'] = 1
        c = 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256'
        c += ':ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305'
        c += ':ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384'
        c += ':ECDHE-ECDSA-AES256-SHA:ECDHE-ECDSA-AES128-SHA'
        c += ':ECDHE-RSA-AES128-SHA:ECDHE-RSA-AES256-SHA:DHE-RSA-AES128-SHA'
        c += ':DHE-RSA-AES256-SHA:AES128-SHA:AES256-SHA:DES-CBC3-SHA'
        c += ':TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384'
        c += ':TLS_CHACHA20_POLY1305_SHA256'
        t = 'TLS_AES_128_GCM_SHA256:TLS_CHACHA20_POLY1305_SHA256'
        t += ':TLS_AES_256_GCM_SHA384'
        objs['ssl'] = {
            'verify': False,
            'verify_hostname': False,
            'cert': '',
            'cipher': c,
            'cipher_tls13': t,
            'sni': '',
            'alpn': ['h2', 'http/1.1'],
            'reuse_session': True,
            'session_ticket': False,
            'curves': '',
        }
        objs['tcp'] = {
            'no_delay': True,
            'keep_alive': True,
            'reuse_port': True,
            'fast_open': False,
            'fast_open_qlen': 20,
        }
        text = json.dumps(objs, indent = 4)
        return text


#----------------------------------------------------------------------
# configure
#----------------------------------------------------------------------
class configure (object):

    def __init__ (self, ininame = None, section = None):
        self.ininame = ininame
        if not self.ininame:
            root = asclib.path.stdpath('config')
            self.ininame = os.path.join(root, 'dler.ini')
        self.config = ascmini.ConfigReader(self.ininame)
        self.section = section and section or 'default'
        self.source = self.config.option(self.section, 'source', '')
        self.source = self.source.strip('\r\n\t ')
        cache = os.path.join(asclib.path.stdpath('cache'), 'dler')
        asclib.path.ensure_path(cache)
        self.cache = os.path.join(cache, '%s.txt' % self.section)
        if not os.path.exists(os.path.dirname(self.cache)):
            os.makedirs(os.path.dirname(self.cache))
        self.items = []
        self.head = {}
        self.reload()

    def __len__ (self):
        return len(self.items)

    def __getitem__ (self, index):
        return self.items[index]

    def __iter__ (self):
        return self.items.__iter__()

    def update (self):
        if not self.source:
            print('source url not set')
            return -1
        url = self.source
        print('updating cache')
        content = ascmini.request_safe(url, timeout = 30)
        if content is None:
            print('failed to fetch source')
            return -1
        import base64
        text =  base64.b64decode(content).decode('utf-8', 'ignore')
        with open(self.cache, 'w') as f:
            f.write(text)
        print('cache updated: %s' % self.cache)
        return 0

    def reload (self):
        if not os.path.exists(self.cache):
            return -1
        self.data = ascmini.posix.load_file_text(self.cache)
        self.head = {}
        self.items = []
        for line in self.data.split('\n'):
            line = line.strip('\r\n\t ')
            if not line:
                continue
            if line.startswith('#'):
                continue
            if line.startswith('REMARKS'):
                _, _, remarks = line.partition('=')
                remarks = remarks.strip('\r\n\t ')
                self.head['remarks'] = remarks
            if line.startswith('STATUS'):
                _, _, status = line.partition('=')
                status = status.strip('\r\n\t ')
                self.head['status'] = status
            if line.startswith('trojan://'):
                p = ProxyInfo(line)
                self.items.append(p)
            elif line.startswith('ss://'):
                p = ProxyInfo(line)
                self.items.append(p)
        return 0


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        c = configure()
        # c.update()
        # print(c.data)
        c.reload()
        for p in c.items:
            print(p)
        print(len(c.items))
        return 0
    def test2():
        dler = ascmini.posix.load_file_text('/home/skywind/scratch/dler.txt').split('\n')
        c1 = dler[0].strip('\r\n\t ')
        c2 = dler[1].strip('\r\n\t ')
        print(c1)
        print(c2)
        print()
        p1 = ProxyInfo(c1)
        print(p1.generate())
        print()
        p2 = ProxyInfo(c2)
        print(p2.generate())
        return 0
    test1()


