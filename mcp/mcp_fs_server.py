"""
只读文件系统 MCP Server

提供的工具：
  - list_directory: 列出目录内容
  - read_file: 读取文件内容
  - get_file_info: 获取文件/目录元信息
  - search_files: 按 glob 模式搜索文件

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


if __name__ == "__main__":
    mcp.run()
