#! /usr/bin/python3
import sys
import os
import netaddr

def is_ip(address):
    try:
        netaddr.IPNetwork(address)
        return True
    except Exception as  e:
        return False

output = []
count = 0

for text in sys.stdin:
    text = text.strip('\r\n\t ')
    if not text:
        continue
    if not is_ip(text):
        continue
    cidr = netaddr.IPNetwork(text)
    output.append(cidr)
    count += 1
    if count % 10000 == 0:
        output = netaddr.cidr_merge(output)

output = netaddr.cidr_merge(output)
for n in output:
    print(n)

