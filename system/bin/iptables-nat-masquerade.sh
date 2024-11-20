#! /bin
network="$1"

if [ -z "$network" ]; then
	echo "usage: $0 {network}"
	exit 1
fi

iptables -t nat -A POSTROUTING -s $network ! -d $network -j MASQUERADE

