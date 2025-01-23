#! /bin/sh
#======================================================================
#
# route-next-destroy.sh - 
#
# Created by skywind on 2025/01/23
# Last Modified: 2025/01/23 15:25:53
#
#======================================================================
ip rule del prio 700 lookup 700
ip rule del prio 710 fwmark 700 lookup main

ip route flush table 700 2> /dev/null

