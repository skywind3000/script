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
# each time when a network interface status is changed.
# Make sure you have "network-manager" installed by "apt-get".
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

APPEND="/etc/script/bin/append-log.sh"
LOG="ifupdown-script.log"
UID="$(id -u)"

[ "$UID" -eq 0 ] && LOG="/var/log/$LOG" || LOG="/tmp/$LOG"

echo "Interface $DEVICE $ACTION" | $APPEND "$LOG"

if [ -x "$FN" ]; then
	IFACE="$DEVICE" "$FN" "$ACTION" 2>&1 | $APPEND "$LOG"
elif [ -x "$FN.sh" ]; then
	IFACE="$DEVICE" "$FN.sh" "$ACTION" 2>&1 | $APPEND "$LOG"
elif [ -x "$FN.bash" ]; then
	IFACE="$DEVICE" "$FN.bash" "$ACTION" 2>&1 | $APPEND "$LOG"
elif [ -x "$FN.zsh" ]; then
	IFACE="$DEVICE" "$FN.zsh" "$ACTION" 2>&1 | $APPEND "$LOG"
elif [ -x "$FN.py" ]; then
	IFACE="$DEVICE" "$FN.py" "$ACTION" 2>&1 | $APPEND "$LOG"
elif [ -x "$FN.lua" ]; then
	IFACE="$DEVICE" "$FN.lua" "$ACTION" 2>&1 | $APPEND "$LOG"
fi

exit 0


