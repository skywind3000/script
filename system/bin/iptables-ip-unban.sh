#! /bin/sh
#======================================================================
#
# iptables-ip-unban.sh - 
#
# Created by skywind on 2024/12/02
# Last Modified: 2024/12/02 21:56:22
#
#======================================================================
IP="$1"

if [ -z "$IP" ]; then
	echo "usage $0 {IP}"
	exit 1
fi

iptables -D INPUT -s $IP -j DROP
iptables -D FORWARD -s $IP -j DROP


