#! /bin/sh
#======================================================================
#
# 10-init-forward.sh - 
#
# Last Modified: 2024/11/23 02:41:47
#
#======================================================================

# enable forwarding
echo 1 > /proc/sys/net/ipv4/ip_forward

# nat masquerade
iptables -t nat -A POSTROUTING -j MASQUERADE


