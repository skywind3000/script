#! /bin/sh
#======================================================================
#
# 10-init-forward.sh - 
#
# Last Modified: 2024/11/23 02:41:47
#
#======================================================================

# enable forwarding
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=1

# tune
sysctl -w net.ipv4.conf.all.accept_redirects=0
sysctl -w net.ipv4.conf.all.send_redirects=0
sysctl -w net.ipv4.conf.all.rp_filter=0
sysctl -w net.ipv4.conf.lo.rp_filter=0

# nat masquerade
iptables -t nat -A POSTROUTING -j MASQUERADE


