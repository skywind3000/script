使用 /etc/script/update_rules.sh 更新生效：

- direct_rules.txt: 直连 ipset DIRECT
- direct_extra.txt: 直连 ipset DIRECT
- vpn1_rules.txt: VPN1 ipset VPN1
- vpn1_extra.txt: VPN1 ipset VPN1
- vpn2_rules.txt: VPN2 ipset VPN1
- vpn2_extra.txt: VPN2 ipset VPN1
- dns1_rules.txt: 域名规则，生成 /etc/dnsmasq.d/50-rules-vpn1.conf
- dns1_extra.txt: 域名规则，生成 /etc/dnsmasq.d/50-rules-vpn1.conf
- dns2_rules.txt: 域名规则，生成 /etc/dnsmasq.d/50-rules-vpn2.conf
- dns2_extra.txt: 域名规则，生成 /etc/dnsmasq.d/50-rules-vpn2.conf

DNS 写法：

- 默认匹配完整域名，即 `google.com` 可以匹配 `google.com` 和 `www.google.com` 但不能匹配 `supergoogle.com`.
- 而 `*google.com` 可以匹配 `google.com` 和 `supergoogle.com`。
- `.google.com` 等同于 `google.com`，但如果你只想匹配 `google.com` 下面的子域名而不匹配 `google.com` 本身，可以用 `*.google.com`。

详细参考 dnsmasq 文档的 "--server=" 部分：

- https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html

前面配置更新了，需要调用：

    sudo /etc/script/tools/update_rules.sh

来刷新实际的 ipset 和 dnsmasq 配置。

注意：DNS 地址 8.8.4.4 会自动加入 VPN1 的 ipset，而 8.8.8.8 会自动加入 VPN2。


