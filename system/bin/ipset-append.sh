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

sed '/^[[:space:]]*$/d' "$2" | sed '/^[[:space:]]*#/d' | sed "s:^:add $SETNAME :g" | ipset -! restore

