使用 /etc/script/update_rules.sh 更新生效：

- direct_rules.txt: 直连 ipset DIRECT
- direct_extra.txt: 直连 ipset DIRECT
- passwall_rules.txt: VPN ipset PASSWALL
- passwall_rules.txt: VPN ipset PASSWALL
- dns_rules.txt: 域名规则，生成 /etc/dnsmasq.d/50-rules.conf
- dns_extra.txt: 域名规则，生成 /etc/dnsmasq.d/50-rules.conf

DNS 写法可以参考 dnsmasq 文档的 "--server=" 部分：

- https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html


