#! /bin/sh
#======================================================================
#
# init.sh - script initialize
#
# Created by skywind on 2024/11/21
# Last Modified: 2024/11/21 03:16:20
#
#======================================================================

# change directory to script home
cd "$(/bin/dirname $0)"
INIT_HOME="$(/bin/pwd)"

# print info
echo "Launching initialization scripts"

# eval each file inside "init" folder
if [ -d "$INIT_HOME/init" ]; then
	for f in $INIT_HOME/init/*; do
		cd "$INIT_HOME/init"
		[ -e "$f" ] && . "$f"
	done
fi

# execute each file inside "run" folder
if [ -d "$INIT_HOME/run" ]; then
	for f in $INIT_HOME/run/*; do
		cd "$INIT_HOME/run"
		[ -x "$f" ] && "$f"
	done
fi


