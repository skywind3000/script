#! /bin/sh

if [ ! -d /home/data/sync ]; then
	echo "/home/data/sync doesn't exist"
	exit 1
elif [ ! -x "$(which rsync)" ]; then
	echo "rsync is not installed"
	exit 1
fi

rsync -avzr --delete -e 'ssh -p32200' skywind@bbtest.skywind.me:/home/data/sync/ /home/data/sync/

exit 0

