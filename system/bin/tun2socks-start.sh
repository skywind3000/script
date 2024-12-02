#! /bin/sh
#======================================================================
#
# tun2socks-start.sh - 
#
# Created by skywind on 2024/12/03
# Last Modified: 2024/12/03 02:16:09
#
#======================================================================
PROGRAM="$0"
BINARY="$1"
DEVICE="$2"
IP="$3"

if [ -z "$IP" ]; then
	echo "Usage: $0 {binary} {device} {ip}  <tun2socks arguments...>"
	echo 'Do not pass "--device xxx" in the tun2socks arguments'
	exit 1
fi

if [ ! -x "$BINARY" ]; then
	echo "Cannot open tun2socks binary(executable) file: $BINARY"
	exit 1
fi

shift
shift
shift

if [ -z "$1" ]; then
	echo "Usage: $PROGRAM {binary} {device} {ip}  <tun2socks arguments...>"
	echo 'Do not pass "--device xxx" in the tun2socks arguments'
	exit 2
fi

echo "Create device: $DEVICE"

ip tuntap add mode tun dev $DEVICE

CODE="$?"

if [ "$CODE" -ne 0 ]; then
	echo "Failed to create device $DEVICE"
	exit 2
fi

ip addr add $IP dev $DEVICE

CODE="$?"

if [ "$CODE" -ne 0 ]; then
	echo "Failed to assign ip to $DEVICE"
	ip tuntap del mode tun dev $DEVICE
	exit 3
fi

ip link set dev $DEVICE up

CODE="$?"

if [ "$CODE" -ne 0 ]; then
	echo "Failed to bring up $DEVICE"
	ip tuntap del mode tun dev $DEVICE
	exit 4
fi

trap "" INT TERM TSTP QUIT EXIT

echo "Starting tun2socks"

echo "Exec: $BINARY" --device "$DEVICE" "$@"

"$BINARY" --device "$DEVICE" "$@"

echo "tun2socks quit"

ip link set $DEVICE down
ip tuntap del mode tun dev $DEVICE

echo "Delete device: $DEVICE"

exit 0


