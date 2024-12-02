#! /bin/sh
#======================================================================
#
# 30-ipset-banlist.sh - 
#
# Created by skywind on 2024/12/02
# Last Modified: 2024/12/02 22:18:37
#
#======================================================================

# create ipset "BANLIST1"
/etc/script/bin/ipset-create.sh BANLIST1

# extend "BANLIST1" with: banlist_rules.txt
if [ -e "../share/banlist_rules.txt" ]; then
	/etc/script/bin/ipset-append.sh BANLIST1 ../share/banlist_rules.txt
fi

# extend "BANLIST1" with: banlist_extra.txt
if [ -e "../share/banlist_extra.txt" ]; then
	/etc/script/bin/ipset-append.sh BANLIST1 ../share/banlist_extra.txt
fi

# ban "BANLIST1"
/etc/script/bin/iptables-ipset-ban.sh BANLIST1



