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
/etc/script/bin/ipset-create.sh VPN1
/etc/script/bin/ipset-create.sh VPN2

# extend "DIRECT" with: direct_rules.txt
if [ -e "../share/direct_rules.txt" ]; then
	/etc/script/bin/ipset-append.sh DIRECT ../share/direct_rules.txt
fi

# extend "DIRECT" with: direct_extra.txt
if [ -e "../share/direct_extra.txt" ]; then
	/etc/script/bin/ipset-append.sh DIRECT ../share/direct_extra.txt
fi

# extend "VPN1" with: vpn1_rules.txt
if [ -e "../share/vpn1_rules.txt" ]; then
	/etc/script/bin/ipset-append.sh VPN1 ../share/vpn1_rules.txt
fi

# extend "VPN1" with: vpn1_extra.txt
if [ -e "../share/vpn1_extra.txt" ]; then
	/etc/script/bin/ipset-append.sh VPN1 ../share/vpn1_extra.txt
fi

# extend "VPN2" with: vpn2_rules.txt
if [ -e "../share/vpn2_rules.txt" ]; then
	/etc/script/bin/ipset-append.sh VPN2 ../share/vpn2_rules.txt
fi

# extend "VPN2" with: vpn2_extra.txt
if [ -e "../share/vpn2_extra.txt" ]; then
	/etc/script/bin/ipset-append.sh VPN2 ../share/vpn2_extra.txt
fi

# enable fwmark
sysctl -w net.ipv4.conf.all.src_valid_mark=1

# iptable set mark 700 for ipset DIRECT
/etc/script/bin/iptables-ipset-mark.sh DIRECT 700

# iptable set mark 800 for ipset VPN1
/etc/script/bin/iptables-ipset-mark.sh VPN1 800

# iptable set mark 801 for ipset VPN2
/etc/script/bin/iptables-ipset-mark.sh VPN2 801

# initialize default route
/etc/script/bin/route-next-init.sh

