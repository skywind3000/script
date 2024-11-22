#! /bin/sh
#
ip route show table all | grep -Eo 'table [^ ]+ ' | sort | uniq

