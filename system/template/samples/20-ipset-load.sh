#! /bin/sh
#======================================================================
#
# 20-ipset-load.sh - 
#
# Last Modified: 2024/11/23 02:43:51
#
#======================================================================

# load ip rules in the ipset "CHINA"
/etc/script/bin/ipset-load.sh CHINA ../share/cn_rules.txt

# extend cnip set with extra rules if existing
if [ -e "../share/cn_extra.txt" ]; then
	/etc/script/bin/ipset-append.sh CHINA ../share/cn_extra.txt
fi

# enable fwmark
sysctl -w net.ipv4.conf.all.src_valid_mark=1

# iptable set mark 666 for ipset CHINA
/etc/script/bin/iptables-mark-set.sh CHINA 666


