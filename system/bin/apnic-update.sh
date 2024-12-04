#! /bin/sh
wget http://ftp.apnic.net/stats/apnic/delegated-apnic-latest

CODE="$?"
NAME="apnic-$(date +%Y%m%d).txt"

if [ "$CODE" -eq 0 ]; then
	mv delegated-apnic-latest "apnic-$(date +%Y%m%d).txt"
	cp $NAME apnic-latest.txt
fi

