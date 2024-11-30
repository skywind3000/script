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

ipset destroy $SETNAME 2> /dev/null
ipset create $SETNAME hash:net hashsize 8192 maxelem 1000000

sed '/^[[:space:]]*$/d' "$2" | sed "s:^:add $SETNAME :g" | ipset restore

