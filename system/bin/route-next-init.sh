#! /bin/sh
#======================================================================
#
# route-next-init.sh - 
#
# Created by skywind on 2025/01/23
# Last Modified: 2025/01/23 15:09:40
#
#======================================================================
ip rule add prio 700 lookup 700
ip rule add prio 710 fwmark 700 lookup main
