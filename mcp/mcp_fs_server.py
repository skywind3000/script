"""
只读文件系统 MCP Server

提供的工具：
  - list_directory: 列出目录内容
  - read_file: 读取文件内容
  - get_file_info: 获取文件/目录元信息
  - search_files: 按 glob 模式搜索文件
  - grep: 在文件内容中搜索匹配的文本或正则表达式

用法：
  直接运行:  python mcp_fs_server.py
  开发调试:  mcp dev mcp_fs_server.py
  配置到 opencode.jsonc:
    "mcp": {
      "fs": {
        "type": "local",
        "command": "python",
        "args": ["mcp_fs_server.py"],
        "enabled": true
      }
    }
"""

import os
import re
import sys
import stat
import datetime
import fnmatch
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ReadOnlyFS")


def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _fmt_time(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _get_birth_time(s: os.stat_result) -> float | None:
    if sys.platform == "win32":
        return s.st_ctime  # Windows: st_ctime 就是创建时间
    return getattr(s, "st_birthtime", None)  # macOS / Linux 3.11+ ext4


def _file_info(path: str) -> dict:
    s = os.stat(path)
    info = {
        "name": os.path.basename(path),
        "path": os.path.abspath(path),
        "type": "directory" if stat.S_ISDIR(s.st_mode) else "file",
        "size": s.st_size,
        "size_human": _fmt_size(s.st_size),
        "modified": _fmt_time(s.st_mtime),
    }
    birth = _get_birth_time(s)
    if birth is not None:
        info["created"] = _fmt_time(birth)
    return info


@mcp.tool()
def list_directory(path: str) -> list[dict]:
    """列出目录内容，返回每个条目的名称、类型和大小。"""
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        raise ValueError(f"不是有效目录: {path}")

    entries = []
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        try:
            entries.append(_file_info(full))
        except OSError:
            entries.append({"name": name, "path": full, "type": "error"})
    return entries


@mcp.tool()
def read_file(path: str, offset: int = 0, limit: int = 2000) -> dict:
    """读取文本文件内容。offset 为起始行号(从0开始)，limit 为最大行数。"""
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise ValueError(f"文件不存在: {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    total = len(lines)
    selected = lines[offset : offset + limit]
    content = "".join(selected)

    return {
        "path": path,
        "total_lines": total,
        "offset": offset,
        "lines_returned": len(selected),
        "content": content,
    }


@mcp.tool()
def get_file_info(path: str) -> dict:
    """获取文件或目录的元信息（大小、修改时间等）。"""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise ValueError(f"路径不存在: {path}")
    return _file_info(path)


@mcp.tool()
def search_files(
    directory: str, pattern: str = "*", max_results: int = 100
) -> list[str]:
    """在目录中递归搜索匹配 glob 模式的文件，返回路径列表。"""
    directory = os.path.abspath(directory)
    if not os.path.isdir(directory):
        raise ValueError(f"不是有效目录: {directory}")

    results = []
    for root, dirs, files in os.walk(directory):
        # 跳过隐藏目录和常见无用目录
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                results.append(os.path.join(root, name))
                if len(results) >= max_results:
                    return results
    return results


# 判断文件是否为二进制文件（检查前 8KB 是否含 null 字节）
_BINARY_CHECK_SIZE = 8192


def _is_binary(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(_BINARY_CHECK_SIZE)
        return b"\x00" in chunk
    except OSError:
        return True


@mcp.tool()
def grep(
    pattern: str,
    path: str,
    file_pattern: str = "*",
    ignore_case: bool = False,
    is_regex: bool = True,
    context_lines: int = 0,
    max_results: int = 200,
    max_file_size: int = 5 * 1024 * 1024,
) -> dict:
    """在文件或目录中搜索匹配的文本/正则表达式，返回匹配的行及上下文。

    Args:
        pattern: 搜索模式（正则表达式或纯文本）。
        path: 要搜索的文件路径或目录路径。若为目录则递归搜索。
        file_pattern: 文件名 glob 过滤（如 "*.py"），仅在搜索目录时生效。
        ignore_case: 是否忽略大小写，默认 False。
        is_regex: pattern 是否为正则表达式，默认 True。若为 False 则按字面文本匹配。
        context_lines: 每个匹配行前后显示的上下文行数，默认 0。
        max_results: 最大返回匹配数，默认 200。
        max_file_size: 跳过超过此大小（字节）的文件，默认 5MB。
    """
    path = os.path.abspath(path)

    # 编译正则
    flags = re.IGNORECASE if ignore_case else 0
    if not is_regex:
        pattern = re.escape(pattern)
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        raise ValueError(f"无效的正则表达式: {e}")

    matches: list[dict] = []
    files_searched = 0
    files_with_matches = 0

    def _grep_file(filepath: str) -> None:
        nonlocal files_searched, files_with_matches

        # 跳过过大的文件
        try:
            if os.path.getsize(filepath) > max_file_size:
                return
        except OSError:
            return

        # 跳过二进制文件
        if _is_binary(filepath):
            return

        files_searched += 1
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            return

        file_has_match = False
        for line_no, line in enumerate(lines, start=1):
            if len(matches) >= max_results:
                return
            if regex.search(line):
                if not file_has_match:
                    file_has_match = True
                    files_with_matches += 1

                match_entry: dict = {
                    "file": filepath,
                    "line": line_no,
                    "content": line.rstrip("\n\r"),
                }

                # 添加上下文行
                if context_lines > 0:
                    before_start = max(0, line_no - 1 - context_lines)
                    before = [
                        l.rstrip("\n\r") for l in lines[before_start : line_no - 1]
                    ]
                    after_end = min(len(lines), line_no + context_lines)
                    after = [l.rstrip("\n\r") for l in lines[line_no:after_end]]
                    if before:
                        match_entry["before"] = before
                    if after:
                        match_entry["after"] = after

                matches.append(match_entry)

    if os.path.isfile(path):
        _grep_file(path)
    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            dirs[:] = [
                d for d in dirs if not d.startswith(".") and d != "__pycache__"
            ]
            for name in sorted(files):
                if fnmatch.fnmatch(name, file_pattern):
                    _grep_file(os.path.join(root, name))
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break
    else:
        raise ValueError(f"路径不存在: {path}")

    return {
        "pattern": pattern,
        "flags": "i" if ignore_case else "",
        "files_searched": files_searched,
        "files_with_matches": files_with_matches,
        "total_matches": len(matches),
        "truncated": len(matches) >= max_results,
        "matches": matches,
    }


if __name__ == "__main__":
    mcp.run()
