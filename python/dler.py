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
import cinit
import ascmini


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

url_regex = ascmini.regex_build(url_rules)


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
        output = []
        return '\n'.join(output)

    def __generate_trojan (self):
        output = []
        return '\n'.join(output)


#----------------------------------------------------------------------
# configure
#----------------------------------------------------------------------
class configure (object):

    def __init__ (self, ininame = None):
        self.ininame = ininame
        if not self.ininame:
            self.ininame = os.path.expanduser('~/.config/dler.ini')
        self.config = ascmini.ConfigReader(self.ininame)
        self.source = self.config.option('default', 'source', '')
        self.source = self.source.strip('\r\n\t ')
        self.cache = os.path.expanduser('~/.cache/dler.txt')
        if not os.path.exists(os.path.dirname(self.cache)):
            os.makedirs(os.path.dirname(self.cache))
        self.items = ''
        self.head = {}
        self.reload()

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
                pass
            elif line.startswith('ss://'):
                pass
        return 0


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        c = configure()
        # c.update()
        print(c.data)
        return 0
    def test2():
        dler = ascmini.posix.load_file_text('/home/skywind/scratch/dler.txt').split('\n')
        c1 = dler[0].strip('\r\n\t ')
        c2 = dler[1].strip('\r\n\t ')
        print(c1)
        print(c2)
        print()
        p1 = ProxyInfo(c1)
        print()
        p2 = ProxyInfo(c2)
        return 0
    test2()


