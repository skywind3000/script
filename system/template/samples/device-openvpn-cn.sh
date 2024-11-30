#! /bin/sh
#======================================================================
#
# device-openvpn-cn.sh - put it in /etc/script/device
#
# Created by skywind on 2024/12/01
# Last Modified: 2024/12/01 00:36:31
#
#======================================================================

# echo "[device] $IFACE $1" | /etc/script/bin/append-log.sh /tmp/record.log

DEV="eth0"
GW="192.168.1.1"
VPN_SERVER="120.232.81.99"
VPN_DEV="tun2"
VPN_GW="10.8.8.1"

if [ "$1" = "up" ]; then
	# install route rules for vpn
	/etc/script/bin/route-vpn-install.sh $DEV $GW $VPN_SERVER $VPN_DEV $VPN_GW

	# china ipset
	ip rule add prio 100 fwmark 666 lookup 666
	ip route add table 666 default via $GW dev $DEV

	# change mtu
	ip link set $VPN_DEV mtu 1400

elif [ "$1" = "postdown" ]; then
	# remove route rules for vpn
	/etc/script/bin/route-vpn-remove.sh $DEV $GW $VPN_SERVER $VPN_DEV $VPN_GW

	# china ipset
	ip rule del prio 100 fwmark 666 lookup 666
	ip route del table 666 default via $GW dev $DEV
fi


