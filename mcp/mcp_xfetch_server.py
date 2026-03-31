"""
xfetch MCP Server

提供的工具：
  - fetch: 抓取网页内容并转为 Markdown，支持按域名规则自动路由 SOCKS5/HTTP 代理

配置文件：
  ~/.config/mcp/xfetch.conf（可选，不存在则全部直连）

用法：
  直接运行:  python mcp_xfetch_server.py
  开发调试:  mcp dev mcp_xfetch_server.py
"""

import configparser
import ipaddress
import logging
import os
import sys
from urllib.parse import urlparse

import requests
from markdownify import markdownify
from readabilipy import simple_json_from_html_string

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("xfetch")

# ---------------------------------------------------------------------------
# 默认值
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0"
)
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".config", "mcp", "xfetch.conf")

# ---------------------------------------------------------------------------
# 代理配置
# ---------------------------------------------------------------------------


class ProxyConfig:
    """解析并管理 xfetch.conf 代理配置。"""

    def __init__(self):
        self.timeout: int = DEFAULT_TIMEOUT
        self.max_body_size: int = DEFAULT_MAX_BODY_SIZE
        self.user_agent: str = DEFAULT_USER_AGENT
        # 有序列表: [(proxy_url, [domain1, domain2, ...]), ...]
        self.rules: list[tuple[str, list[str]]] = []

    @classmethod
    def load(cls) -> "ProxyConfig":
        cfg = cls()
        if not os.path.isfile(CONFIG_PATH):
            logger.info("配置文件不存在 (%s)，全部直连", CONFIG_PATH)
            return cfg

        parser = configparser.RawConfigParser()
        parser.optionxform = str  # 保持大小写
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                parser.read_file(f)
        except configparser.Error as e:
            raise RuntimeError(f"配置文件格式错误: {CONFIG_PATH}: {e}") from e

        # [default] 段
        if parser.has_section("default"):
            sec = dict(parser.items("default"))
            cfg.timeout = int(sec.get("timeout", DEFAULT_TIMEOUT))
            cfg.max_body_size = int(sec.get("max_body_size", DEFAULT_MAX_BODY_SIZE))
            cfg.user_agent = sec.get("user_agent", DEFAULT_USER_AGENT)

        # 代理段
        for section in parser.sections():
            if section == "default":
                continue
            # section 头即代理地址
            proxy_url = section
            domains = []
            # configparser 把每行 key=value 或 key（无值）都当作 option
            for key in parser.options(section):
                domain = key.strip()
                if domain:
                    domains.append(domain.lower())
            if domains:
                cfg.rules.append((proxy_url, domains))

        logger.info(
            "已加载配置: timeout=%d, max_body_size=%d, 代理规则 %d 条",
            cfg.timeout,
            cfg.max_body_size,
            len(cfg.rules),
        )
        return cfg


def _domain_matches(hostname: str, pattern: str) -> bool:
    """NO_PROXY 风格：裸域名匹配自身及所有子域名。"""
    return hostname == pattern or hostname.endswith("." + pattern)


def _is_local_address(host: str) -> bool:
    """判断 host 是否为局域网/环回/链路本地地址。"""
    if host.lower() == "localhost":
        return True
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return False


def _resolve_proxy(config: ProxyConfig, url: str) -> dict | None:
    """根据 URL 和配置返回 requests 可用的 proxies 字典，无匹配返回 None。"""
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    scheme = parsed.scheme  # http / https

    if not hostname:
        return None

    # 先检查配置中是否有精确匹配该 host 的代理规则
    matched_proxy = None
    for proxy_url, domains in config.rules:
        for domain in domains:
            if _domain_matches(hostname, domain):
                matched_proxy = proxy_url
                break
        if matched_proxy:
            break

    # 局域网地址：仅在有精确匹配规则时才走代理
    if _is_local_address(hostname) and matched_proxy is None:
        return None

    if matched_proxy is None:
        return None

    # socks5:// → socks5h://（DNS 由远端解析）
    actual_proxy = matched_proxy
    if actual_proxy.startswith("socks5://"):
        actual_proxy = "socks5h://" + actual_proxy[len("socks5://"):]

    return {
        "http": actual_proxy,
        "https": actual_proxy,
    }


# ---------------------------------------------------------------------------
# HTML → Markdown 转换
# ---------------------------------------------------------------------------


def _html_to_markdown(html: str, url: str) -> str:
    """使用 readabilipy 提取正文，再用 markdownify 转为 Markdown。"""
    try:
        article = simple_json_from_html_string(html, use_readability=False)
        content_html = article.get("content") or ""
        if not content_html:
            # readabilipy 未能提取到正文，回退到全文
            content_html = html
    except Exception:
        content_html = html

    md = markdownify(content_html, strip=["img", "script", "style"])
    # 清理多余空行
    lines = md.splitlines()
    cleaned = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                cleaned.append("")
        else:
            blank_count = 0
            cleaned.append(line)
    return "\n".join(cleaned).strip()


# ---------------------------------------------------------------------------
# 内容判断
# ---------------------------------------------------------------------------


def _is_html(content_type: str) -> bool:
    """判断 Content-Type 是否为 HTML。"""
    ct = content_type.lower().split(";")[0].strip()
    return ct in ("text/html", "application/xhtml+xml")


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp_server = FastMCP("xfetch")

# 启动时加载配置
_config = ProxyConfig.load()


@mcp_server.tool()
def fetch(
    url: str,
    max_length: int = 5000,
    start_index: int = 0,
    raw: bool = False,
) -> str:
    """抓取指定 URL 的内容，默认将 HTML 转为 Markdown 返回。

    Args:
        url: 要抓取的 URL。
        max_length: 返回内容最大字符数，默认 5000。
        start_index: 从第几个字符开始返回（用于分页读取长内容），默认 0。
        raw: true 返回原始 HTML，false 返回 Markdown，默认 false。
    """
    # 构建请求参数
    proxies = _resolve_proxy(_config, url)
    headers = {"User-Agent": _config.user_agent}

    try:
        resp = requests.get(
            url,
            headers=headers,
            proxies=proxies,
            timeout=_config.timeout,
            stream=True,
        )
    except requests.exceptions.Timeout:
        return f"错误: 请求超时（{_config.timeout} 秒）"
    except requests.exceptions.RequestException as e:
        return f"错误: 请求失败: {e}"

    # 读取响应体，限制大小
    chunks = []
    total_size = 0
    truncated_by_size = False
    try:
        for chunk in resp.iter_content(chunk_size=8192, decode_unicode=False):
            chunks.append(chunk)
            total_size += len(chunk)
            if total_size >= _config.max_body_size:
                truncated_by_size = True
                break
    except requests.exceptions.RequestException as e:
        return f"错误: 读取响应体失败: {e}"
    finally:
        resp.close()

    raw_bytes = b"".join(chunks)

    # 检测编码
    encoding = resp.encoding or "utf-8"
    try:
        text = raw_bytes.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        text = raw_bytes.decode("utf-8", errors="replace")

    if truncated_by_size:
        text += f"\n\n[内容已截断：响应体超过 {_config.max_body_size} 字节上限]"

    # 转换内容
    content_type = resp.headers.get("Content-Type", "")
    if _is_html(content_type) and not raw:
        content = _html_to_markdown(text, url)
    else:
        content = text

    total_len = len(content)

    # 分页截取
    segment = content[start_index: start_index + max_length]

    result_parts = [segment]

    remaining = total_len - start_index - len(segment)
    if remaining > 0:
        next_index = start_index + len(segment)
        result_parts.append(
            f"\n\n---\n"
            f"内容已截断。总长度 {total_len} 字符，"
            f"已返回 {start_index} 到 {next_index} 的内容。"
            f"使用 start_index={next_index} 继续读取剩余 {remaining} 字符。"
        )

    return "".join(result_parts)


if __name__ == "__main__":
    mcp_server.run()
