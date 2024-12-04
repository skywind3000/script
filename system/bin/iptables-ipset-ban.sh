#! /bin/sh
#======================================================================
#
# iptables-set-ban.sh - ban IPs from ipset
#
# Created by skywind on 2024/12/02
# Last Modified: 2024/12/02 22:00:10
#
#======================================================================
SETNAME="$1"

if [ -z "$SETNAME" ]; then
	echo "usage: $0 {SETNAME}"
	exit 1
fi

iptables -I INPUT -m set --match-set "$SETNAME" src -j DROP

# iptables -I PREROUTING -t raw -m set --match-set "$SETNAME" src -j DROP

