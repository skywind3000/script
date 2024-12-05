#! /bin/sh

NAME="$1"

if [ -z "$NAME" ]; then
	echo "usage: $0 {apnic-list}"
	exit 1
elif [ ! -e "$NAME" ]; then
	echo "failed to open: $NAME"
	exit 1
fi

cat "$NAME" | grep 'ipv4' | grep 'CN' | \
	awk -F '|' '{print $4 "/" 32-log($5)/log(2)}'  | \
	python3 /home/data/script/system/utils/cidr_merge.py > "cn-$NAME"

cat "$NAME" | grep 'ipv4' | grep -v 'CN' | grep -v '*' | \
	awk -F '|' '{print $4 "/" 32-log($5)/log(2)}' | \
	python3 /home/data/script/system/utils/cidr_merge.py > "en-$NAME"

