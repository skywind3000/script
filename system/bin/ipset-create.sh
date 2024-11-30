#! /bin/sh

SETNAME="$1"

if [ -z "$SETNAME" ]; then
	echo "usage: $0 {SETNAME}"
	exit 1
fi

ipset destroy $SETNAME 2> /dev/null
ipset create $SETNAME hash:net hashsize 8192 maxelem 1000000

