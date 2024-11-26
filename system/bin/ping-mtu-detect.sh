#! /bin/bash

destination_ip="$1"
packet_size=1200

if [ -z "$destination_ip" ]; then
	echo "usage: $0 {ip}"
	exit 1
fi

if [ -z "$BASH_VERSION" ] && [ -z "$ZSH_VERSION" ]; then
	echo "bash or zsh is required"
	exit 1
fi


while true; do
	ping -M do -c 1 -s $packet_size $destination_ip &> /dev/null
	if [ $? -ne 0 ]; then
		echo "Maximum MTU size: $((packet_size + 28 - 2))"
		break
	fi
	packet_size=$((packet_size + 2))
done

exit 0

