# xfetch-mcp 需求文档

## 一、概述

基于 Python 实现的 MCP Server，提供 `fetch` tool，用于抓取网页内容并转为 Markdown。支持按域名规则自动路由 SOCKS5/HTTP 代理。

## 二、依赖模块

| 模块 | 用途 |
|------|------|
| `requests` | HTTP 请求 |
| `PySocks` | SOCKS5 代理支持 |
| `readabilipy` | HTML 正文提取 |
| `markdownify` | HTML 转 Markdown |
| `mcp` (Python SDK) | MCP 协议实现 |

## 三、Tool 定义

### fetch

抓取指定 URL 的内容，默认将 HTML 转为 Markdown 返回。

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | 是 | - | 要抓取的 URL |
| `max_length` | int | 否 | 5000 | 返回内容最大字符数 |
| `start_index` | int | 否 | 0 | 从第几个字符开始返回（用于分页读取长内容） |
| `raw` | bool | 否 | false | true 返回原始 HTML，false 返回 Markdown |

#### 返回行为

- 默认将 HTML 转为 Markdown 返回（使用 readabilipy 提取正文 + markdownify 转换）
- `raw=true` 时返回原始 HTML
- 超过 `max_length` 时截断，并提示使用 `start_index` 继续读取
- 非 HTML 内容（JSON、纯文本等）直接返回原文

## 四、代理配置

### 配置文件路径

`~/.config/mcp/xfetch.conf`

### 配置文件不存在时

全部直连，功能与普通 fetch MCP 一致。

### 格式示例

```ini
[default]
timeout = 30
max_body_size = 10485760
user_agent = Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0

[socks5://localhost:1080]
google.com
youtube.com

[http://localhost:1085]
twitter.com
python.org
```

### [default] 段 -- 全局默认配置

| 键 | 默认值 | 说明 |
|----|--------|------|
| `timeout` | `30` | 请求超时，单位秒 |
| `max_body_size` | `10485760` | 响应体大小上限，单位字节（默认 10MB） |
| `user_agent` | `Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0` | 请求时使用的 User-Agent |

### 代理段

section 头为代理地址（`[socks5://...]` 或 `[http://...]`），每行一个域名。

**SOCKS5 DNS 解析：** 配置中写 `socks5://` 时，实际以 `socks5h://` 方式工作，即 DNS 解析由远端代理服务器完成（而非本地解析）。这是为了避免本地 DNS 污染或泄漏，适用于需要翻墙的场景。实现上，传给 `requests` 的 proxies 参数统一使用 `socks5h://` 协议前缀。

使用 NO_PROXY 风格后缀匹配规则：

| 配置写法 | 匹配范围 |
|----------|----------|
| `google.com` | `google.com` 本身 + 所有子域名（`www.google.com`、`mail.google.com` 等） |
| `python.org` | `python.org` 本身 + `docs.python.org`、`pypi.python.org` 等 |

匹配逻辑：

```python
def domain_matches(hostname: str, pattern: str) -> bool:
    """NO_PROXY 风格：裸域名匹配自身及所有子域名"""
    return hostname == pattern or hostname.endswith("." + pattern)
```

优先级：配置文件中先出现的规则优先匹配。

无匹配时：直连（不走代理）。

### 局域网地址处理

以下地址始终直连，**除非**配置文件中有明确的代理规则覆盖：

- IPv4 私有地址：`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`
- 链路本地地址：`169.254.0.0/16`
- 环回地址：`127.0.0.0/8`（含 `localhost`）
- IPv6 本地地址：`::1`、`fe80::/10`、`fc00::/7`

判断逻辑：解析 URL 中的 host，若为 IP 地址则用 Python 标准库 `ipaddress` 模块判断是否为私有/环回/链路本地地址；若为 `localhost` 则直接视为本地。仅当配置文件中存在精确匹配该 IP 或 `localhost` 的代理规则时，才走代理。

## 五、边界处理

| 场景 | 行为 |
|------|------|
| 配置文件不存在 | 全部直连，等同普通 fetch MCP |
| 配置文件格式错误 | 启动时报错，日志提示具体行号 |
| 响应体超过 `max_body_size` | 截断并返回提示信息 |
| 请求超时 | 返回错误信息，包含超时时长 |
| 局域网地址无明确代理规则 | 直连，不走任何代理 |
