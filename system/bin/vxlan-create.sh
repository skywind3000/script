#! /bin/sh
name="$1"
vni="$2"
remote="$3"
dev="$4"

if [ -z "$dev" ]; then
	echo "usage: $0 {name} {vni} {remote} {dev}"
	exit 1
fi

ip link add $name type vxlan id $vni dstport 4789 \
	remote $remote dev $dev

