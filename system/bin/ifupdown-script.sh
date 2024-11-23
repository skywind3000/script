#! /bin/sh
#======================================================================
#
# ifupdown-script.sh - run script in /etc/script/device
#
# Created by skywind on 2024/11/23
# Last Modified: 2024/11/23 23:07:08
#
# USAGE:
#
#     sudo /etc/script/bin/ifupdown-script.sh --install
#
# And, this script will run the command: 
#
#     /etc/script/device/$IFACE {up|down|preup|postdown}
#
# each time when a network interface status is changed
#
#======================================================================
DEVICE="$1"
ACTION="$2"


if [ "$1" = "--install" ]; then
	FN="/etc/network/if-up.d/90-ifupdown-script"
	echo "#! /bin/sh" > $FN
	echo '/etc/script/bin/ifupdown-script.sh "$IFACE" up' >> $FN
	chmod 755 $FN
	FN="/etc/network/if-down.d/10-ifupdown-script"
	echo "#! /bin/sh" > $FN
	echo '/etc/script/bin/ifupdown-script.sh "$IFACE" down' >> $FN
	chmod 755 $FN
	FN="/etc/network/if-post-down.d/10-ifupdown-script"
	echo "#! /bin/sh" > $FN
	echo '/etc/script/bin/ifupdown-script.sh "$IFACE" postdown' >> $FN
	chmod 755 $FN
	FN="/etc/network/if-pre-up.d/90-ifupdown-script"
	echo "#! /bin/sh" > $FN
	echo '/etc/script/bin/ifupdown-script.sh "$IFACE" preup' >> $FN
	chmod 755 $FN
elif [ -z "$ACTION" ]; then
	echo "usage: $0 {device} {up|down}"
	exit 1
fi

FN="/etc/script/device/$DEVICE"

if [ -x "$FN" ]; then
	IFACE="$DEVICE" "$FN" "$ACTION"
elif [ -x "$FN.sh" ]; then
	IFACE="$DEVICE" "$FN.sh" "$ACTION"
elif [ -x "$FN.bash" ]; then
	IFACE="$DEVICE" "$FN.bash" "$ACTION"
elif [ -x "$FN.zsh" ]; then
	IFACE="$DEVICE" "$FN.zsh" "$ACTION"
elif [ -x "$FN.py" ]; then
	IFACE="$DEVICE" "$FN.py" "$ACTION"
elif [ -x "$FN.lua" ]; then
	IFACE="$DEVICE" "$FN.lua" "$ACTION"
fi

exit 0

