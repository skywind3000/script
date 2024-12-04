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
CPID=0

if [ "$CODE" -ne 0 ]; then
	echo "Failed to bring up $DEVICE"
	ip tuntap del mode tun dev $DEVICE
	exit 4
fi

_tun2socks_terminate() {
	SIG=$(($? - 128))
	echo "received signal: $SIG"
	if [ $CPID -ne 0 ]; then
		echo "terminate child"
		kill $CPID 2> /dev/null
	fi
}

trap "_tun2socks_terminate" INT TERM TSTP QUIT EXIT

echo "Starting tun2socks (script $$):"

echo "Exec: $BINARY" --device "$DEVICE" "$@"

"$BINARY" --device "$DEVICE" "$@" &

CPID=$!

wait $CPID

CPID=0

echo "tun2socks quit"

ip link set $DEVICE down
ip tuntap del mode tun dev $DEVICE

echo "Delete device: $DEVICE"

exit 0


