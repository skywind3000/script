#! /bin/sh

# echo "[device] $IFACE $1" | /etc/script/bin/append-log.sh /tmp/record.log

DEV="eth0"
GW="10.66.5.1"
VPN_SERVER="111.229.152.96"
VPN_DEV="tun2"
VPN_GW="10.8.8.1"
VPN_SUBNET="10.8.8.0/24"

if [ "$1" = "up" ]; then
	# install route rules for vpn
	/etc/script/bin/route-direct-install.sh $DEV $GW $VPN_SERVER $VPN_DEV $VPN_GW $VPN_SUBNET

	# change mtu
	# ip link set $VPN_DEV mtu 1400

elif [ "$1" = "postdown" ]; then
	# remove route rules for vpn
	/etc/script/bin/route-direct-remove.sh $DEV $GW $VPN_SERVER $VPN_DEV $VPN_GW $VPN_SUBNET
fi

