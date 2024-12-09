#! /bin/sh

# echo "[device] $IFACE $1" | /etc/script/bin/append-log.sh /tmp/record.log

DEV="eth0"
GW="192.168.1.1"
VPN_SERVER="108.61.217.246"
VPN_DEV="tun1"
VPN_GW="10.8.108.24"

if [ "$1" = "up" ]; then
	# install route rules for vpn
	/etc/script/bin/route-direct-install.sh $DEV $GW $VPN_SERVER $VPN_DEV $VPN_GW

	# change mtu
	# ip link set $VPN_DEV mtu 1400

elif [ "$1" = "postdown" ]; then
	# remove route rules for vpn
	/etc/script/bin/route-direct-remove.sh $DEV $GW $VPN_SERVER $VPN_DEV $VPN_GW

	# china ipset
	ip rule del prio 100 fwmark 666 lookup 666
	ip route del table 666 default via $GW dev $DEV
fi


