#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# http.py - 
#
# Created by skywind on 2024/12/24
# Last Modified: 2024/12/24 14:08:15
#
#======================================================================
from __future__ import print_function, unicode_literals
import sys
import time
import os


#----------------------------------------------------------------------
# http_request
#----------------------------------------------------------------------
def request(url, data = None, post = False, header = None, opts = None):
    headers = []
    import urllib
    import ssl
    status = -1
    if not opts:
        opts = {}
    timeout = opts.get('timeout', 10)
    proxy = opts.get('proxy', None)
    if sys.version_info[0] >= 3:
        import urllib.parse, urllib.request, urllib.error
        if data is not None:
            if isinstance(data, dict):
                data = urllib.parse.urlencode(data)
        if not post:
            if data is None:
                req = urllib.request.Request(url)
            else:
                mark = '?' in url and '&' or '?'
                req = urllib.request.Request(url + mark + data)
        else:
            data = data is not None and data or ''
            if not isinstance(data, bytes):
                # pylint: disable=redefined-variable-type
                data = data.encode('utf-8', 'ignore')   # noqa
            req = urllib.request.Request(url, data)
        if header:
            for k, v in header.items():
                req.add_header(k, v)
        handlers = []
        if proxy:
            p = {'http': proxy, 'https': proxy}
            proxy_handler = urllib.request.ProxyHandler(p)
            handlers.append(proxy_handler)
        try:
            opener = urllib.request.build_opener(*handlers)
            res = opener.open(req, timeout = timeout)
            headers = res.getheaders()
        except urllib.error.HTTPError as e:
            return e.code, str(e.message), None
        except urllib.error.URLError as e:
            return -1, str(e), None
        except socket.timeout:
            return -2, 'timeout', None
        except ssl.SSLError:
            return -2, 'SSLError', None
        content = res.read()
        status = res.getcode()
        res.close()
    else:
        import urllib2
        if data is not None:
            if isinstance(data, dict):
                part = {}
                for key in data:
                    val = data[key]
                    if isinstance(key, unicode):
                        key = key.encode('utf-8')
                    if isinstance(val, unicode):
                        val = val.encode('utf-8')
                    part[key] = val
                data = urllib.urlencode(part)
            if not isinstance(data, bytes):
                data = data.encode('utf-8', 'ignore')
        if not post:
            if data is None:
                req = urllib2.Request(url)
            else:
                mark = '?' in url and '&' or '?'
                req = urllib2.Request(url + mark + data)
        else:
            req = urllib2.Request(url, data is not None and data or '')
        if header:
            for k, v in header.items():
                req.add_header(k, v)
        try:
            res = urllib2.urlopen(req, timeout = timeout)
            content = res.read()
            status = res.getcode()
            if res.info().headers:
                for line in res.info().headers:
                    line = line.rstrip('\r\n\t')
                    pos = line.find(':')
                    if pos < 0:
                        continue
                    key = line[:pos].rstrip('\t ')
                    val = line[pos + 1:].lstrip('\t ')
                    headers.append((key, val))
        except urllib2.HTTPError as e:
            return e.code, str(e.message), None
        except urllib2.URLError as e:
            return -1, str(e), None
        except socket.timeout:
            return -2, 'timeout', None
        except ssl.SSLError:
            return -2, 'SSLError', None
    return status, content, headers


#----------------------------------------------------------------------
# request with retry
#----------------------------------------------------------------------
def request_safe(url, timeout = 10, retry = 3, verbose = True, delay = 1):
    opts = {'timeout': timeout}
    for i in range(retry):
        if verbose:
            print('%s: %s'%(i == 0 and 'request' or 'retry', url))
        time.sleep(delay)
        code, content, _ = request(url, opts = opts)
        if code == 200:
            return content
    return None


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        
        return 0
    test1()

