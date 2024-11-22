#! /bin/sh

LOGFILE="$1"

if [ "$LOGFILE" = "-h" ] || [ "$LOGFILE" = "--help" ]; then
	echo "usage: $0 {logfile}"
	exit 1
fi

_prefix_timestamp() {
	[ -z "$LOGTYPE" ] && N="" || N=" [$LOGTYPE]"
	while read R; do
		echo "[$(date '+%Y-%m-%d %H:%M:%S')]$N $R"
	done
}


if [ -z "$LOGFILE" ]; then
	_prefix_timestamp
else
	_prefix_timestamp | tee -a "$LOGFILE"
fi


