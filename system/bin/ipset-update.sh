#! /bin/sh

SETNAME="$1"
FILENAME="$2"

if [ "$FILENAME" = "" ]; then
	echo "usage: $0 SETNAME filename"
	exit 1
fi

if [ ! -e "$FILENAME" ]; then
	echo "error: missing $FILENAME"
	exit 1
fi

ipset flush $SETNAME

sed "s:^:add $SETNAME :g" "$2" | ipset restore

