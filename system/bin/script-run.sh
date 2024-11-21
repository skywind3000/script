#! /bin/sh
#======================================================================
#
# script-run.sh - execute each file inside given directory
#
# Created by skywind on 2024/11/21
# Last Modified: 2024/11/21 11:02:13
#
#======================================================================
directory="$1"

if [ -z "$directory" ]; then
	echo "usage: $0 {directory}"
	exit 1
fi

if [ ! -d "$directory" ]; then
	echo "invalid path: $directory"
	exit 1
fi

# execute each file inside root folder
for f in $directory/*; do
	[ -x "$f" ] && "$f"
done

exit 0

