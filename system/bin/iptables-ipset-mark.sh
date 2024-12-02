#! /bin/sh
#======================================================================
#
# iptables-set-mark.sh - 
#
# Created by skywind on 2024/12/02
# Last Modified: 2024/12/02 22:03:52
#
#======================================================================

SETNAME="$1"
MARK="$2"

if [ -z "$MARK" ]; then
	echo "usage: $0 {SETNAME} {MARK}"
	exit 1
fi

# for application output
iptables -I OUTPUT -t mangle -m set --match-set $SETNAME dst -j MARK --set-mark $MARK

# for packet forward
iptables -I PREROUTING -t mangle -m set --match-set $SETNAME dst -j MARK --set-mark $MARK


