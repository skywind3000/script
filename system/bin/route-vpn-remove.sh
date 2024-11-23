#! /bin/sh
#======================================================================
#
# route-vpn-remove.sh - 
#
# Created by skywind on 2024/11/23
# Last Modified: 2024/11/23 20:08:16
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
ip route del $VPN_SERVER via $GATEWAY dev $DEVICE

# vpn sub network
if [ -n "$VPN_SUBNET" ]; then
	ip route del $VPN_SUBNET dev $VPN_DEVICE 
fi

# create new rule to overshadow default routing entry
ip route del 0.0.0.0/1 via $VPN_GATEWAY dev $VPN_DEVICE
ip route del 128.0.0.0/1 via $VPN_GATEWAY dev $VPN_DEVICE


