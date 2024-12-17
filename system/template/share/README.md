使用 /etc/script/update_rules.sh 更新生效：

- direct_rules.txt: 直连 ipset DIRECT
- direct_extra.txt: 直连 ipset DIRECT
- passwall_rules.txt: VPN ipset PASSWALL
- passwall_rules.txt: VPN ipset PASSWALL
- dns_rules.txt: 域名规则，生成 /etc/dnsmasq.d/50-rules.conf
- dns_extra.txt: 域名规则，生成 /etc/dnsmasq.d/50-rules.conf

DNS 写法：

- 默认匹配完整域名，即 `google.com` 可以匹配 `google.com` 和 `www.google.com` 但不能匹配 `supergoogle.com`.
- 而 `*google.com` 可以匹配 `google.com` 和 `supergoogle.com`。
- `.google.com` 等同于 `google.com`，但如果你只想匹配 `google.com` 下面的子域名而不匹配 `google.com` 本身，可以用 `*.google.com`。

详细参考 dnsmasq 文档的 "--server=" 部分：

- https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html


