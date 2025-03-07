#! /bin/sh
#======================================================================
#
# iptables-dnat-add.sh - DNAT forwarding (required ip_forward enabled)
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
	echo "usage: $0 {tcp/udp} {srcip} {srcport} {dstip} {dstport}"
	exit 1
fi

iptables -t nat -A PREROUTING -p $PROTO -d $SRCIP --dport $SRCPORT -j DNAT --to-destination $DSTIP:$DSTPORT
iptables -t nat -A POSTROUTING -p $PROTO -d $DSTIP --dport $DSTPORT -j SNAT --to-source $SRCIP

