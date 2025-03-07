#! /bin/sh
#======================================================================
#
# iptables-dnat-add.sh - DNAT forwarding
#
# Created by skywind on 2025/03/07
# Last Modified: 2025/03/07 11:37:41
#
#======================================================================
PROTO="$1"
SRCIP="$2"
SRCPORT="$3"
DSTIP="$4"
DSTPORT="$5"

if [ -z "$DSTPORT" ]; then
	echo "usage: $0 {interface} {tcp/udp} {srcip} {srcport} {dstip} {dstport}"
	exit 1
fi

iptables -t nat -D PREROUTING -p $PROTO -d $SRCIP --dport $SRCPORT -j DNAT --to-destination $DSTIP:$DSTPORT
iptables -t nat -D POSTROUTING -p $PROTO -d $DSTIP --dport $DSTPORT -j SNAT --to-source $SRCIP


