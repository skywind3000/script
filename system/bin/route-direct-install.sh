#! /bin/sh
#======================================================================
#
# route-direct-install.sh - 
#
# Created by skywind on 2024/12/01
# Last Modified: 2024/12/01 01:56:35
#
#======================================================================
DEVICE="$1"
GATEWAY="$2"
VPN_SERVER="$3"
VPN_DEVICE="$4"
VPN_GATEWAY="$5"
VPN_SUBNET="$6"

if [ -z "$VPN_GATEWAY" ]; then
	echo "usage: $0 {dev} {gw} {vpn_server} {vpn_dev} {vpn_gw} [vpn_subnet]"
	echo "example:"
	echo "$0 eth0 192.168.1.1 202.115.8.13 tun0 10.8.2.1 10.8.2.0/24"
	exit 1
fi


# vpn server use default gateway
ip route add table 200 $VPN_SERVER via $GATEWAY dev $DEVICE
ip rule add prio 100 lookup 200

# direct link use default gateway
ip rule add prio 101 fwmark 700 lookup main

# vpn sub network
if [ -n "$VPN_SUBNET" ]; then
	ip route add table 201 $VPN_SUBNET dev $VPN_DEVICE
fi

# passwall link use vpn gateway
ip route add table 201 default via $VPN_GATEWAY dev $VPN_DEVICE
ip rule add prio 102 fwmark 701 lookup 201


