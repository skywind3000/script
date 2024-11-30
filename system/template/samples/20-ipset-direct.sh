#! /bin/sh
#======================================================================
#
# 20-ipset-direct.sh - 
#
# Created by skywind on 2024/12/01
# Last Modified: 2024/12/01 00:44:01
#
#======================================================================

# create ipset "DIRECT" and "PASSWALL"
/etc/script/bin/ipset-create.sh DIRECT
/etc/script/bin/ipset-create.sh PASSWALL

# extend "DIRECT" with: direct_rules.txt
if [ -e "../share/direct_rules.txt" ]; then
	/etc/script/bin/ipset-append.sh DIRECT ../share/direct_rules.txt
fi

# extend "DIRECT" with: direct_extra.txt
if [ -e "../share/direct_extra.txt" ]; then
	/etc/script/bin/ipset-append.sh DIRECT ../share/direct_extra.txt
fi

# extend "PASSWALL" with: passwall_rules.txt
if [ -e "../share/passwall_rules.txt" ]; then
	/etc/script/bin/ipset-append.sh PASSWALL ../share/passwall_rules.txt
fi

# extend "PASSWALL" with: passwall_extra.txt
if [ -e "../share/passwall_extra.txt" ]; then
	/etc/script/bin/ipset-append.sh PASSWALL ../share/passwall_extra.txt
fi

# enable fwmark
sysctl -w net.ipv4.conf.all.src_valid_mark=1

# iptable set mark 700 for ipset DIRECT
/etc/script/bin/iptables-mark-set.sh DIRECT 700

# iptable set mark 701 for ipset PASSWALL
/etc/script/bin/iptables-mark-set.sh PASSWALL 701


