#! /bin
network="$1"
remove="$2"

if [ -z "$network" ]; then
	echo "usage: $0 {network}"
	exit 1
fi

if [ "$remove" != "-" ]; then
	mode="-A"
	echo "append"
else
	mode="-D"
	echo "remove"
fi

if [ "$network" != "true" ]; then
	iptables -t nat $mode POSTROUTING -s $network ! -d $network -j MASQUERADE
else
	iptables -t nat $mode POSTROUTING -j MASQUERADE
fi

