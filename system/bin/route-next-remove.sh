#! /bin/sh
#======================================================================
#
# route-next-remove.sh - 
#
# Created by skywind on 2025/01/23
# Last Modified: 2025/01/23 15:35:04
#
#======================================================================
INDEX="$1"
DEVICE="$2"
GATEWAY="$3"
VPN_SERVER="$4"
VPN_DEVICE="$5"
VPN_GATEWAY="$6"
VPN_SUBNET="$7"

if [ -z "$VPN_GATEWAY" ]; then
	echo "usage: $0 {index} {dev} {gw} {vpn_server} {vpn_dev} {vpn_gw} [vpn_subnet]"
	echo "example:"
	echo "$0 0 eth0 192.168.1.1 202.115.8.13 tun0 10.8.2.1 10.8.2.0/24"
	exit 1
fi

# vpn server use default gateway
ip route del table 700 $VPN_SERVER via $GATEWAY dev $DEVICE

# vpn sub network
if [ -n "$VPN_SUBNET" ]; then
	ip route del table 700 $VPN_SUBNET dev $VPN_DEVICE
fi


# vpn name calculation
NAME="$((800+INDEX))"

# vpn link use vpn gateway
ip route del table $NAME default via $VPN_GATEWAY dev $VPN_DEVICE
ip rule del prio $NAME fwmark $NAME lookup $NAME
ip route flush table $NAME


