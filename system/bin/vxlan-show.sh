#! /bin/sh
name="$1"

if [ -z "$name" ]; then
	echo "usage: $0 {name}"
	exit 1
fi

ip -d link show $name

