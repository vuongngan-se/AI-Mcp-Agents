"""
Linux System MCP Server
Cung cấp các công cụ tương tác, quản trị và giám sát hệ thống Linux theo chuẩn MCP.
"""

import os
import platform
import shutil
import subprocess
from typing import Any, Dict, List
from mcp.server.fastmcp import FastMCP

# Khởi tạo MCP Server với tên 'linux-system-server'
mcp = FastMCP("linux-system-server")


@mcp.tool()
def get_system_info() -> Dict[str, Any]:
    """Lấy thông tin tổng quan về phần cứng, hệ điều hành (OS), CPU, RAM và Disk của máy Linux."""
    uname = platform.uname()

    # Thông tin bộ nhớ RAM (qua /proc/meminfo)
    mem_info = {}
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip()
                    if key in ["MemTotal", "MemFree", "MemAvailable"]:
                        mem_info[key] = val
    except Exception as e:
        mem_info["error"] = str(e)

    # Thông tin ổ đĩa (Root partition)
    disk = shutil.disk_usage("/")
    disk_info = {
        "total_gb": round(disk.total / (1024**3), 2),
        "used_gb": round(disk.used / (1024**3), 2),
        "free_gb": round(disk.free / (1024**3), 2),
        "percent_used": round((disk.used / disk.total) * 100, 1),
    }

    # Uptime
    uptime_str = ""
    try:
        res = subprocess.run(
            ["uptime", "-p"], capture_output=True, text=True, timeout=5
        )
        uptime_str = res.stdout.strip()
    except Exception:
        uptime_str = "N/A"

    return {
        "os_name": uname.system,
        "hostname": uname.node,
        "kernel_release": uname.release,
        "architecture": uname.machine,
        "cpu_count": os.cpu_count(),
        "memory": mem_info,
        "disk_root": disk_info,
        "uptime": uptime_str,
    }


@mcp.tool()
def execute_command(command: str, timeout: int = 30) -> Dict[str, Any]:
    """Thực thi một câu lệnh shell/bash trên hệ thống Linux và trả về stdout, stderr, mã thoát (exit_code).

    Args:
        command: Lệnh shell cần chạy (ví dụ: 'df -h', 'ls -la /var/log', 'systemctl status sshd').
        timeout: Thời gian tối đa (giây) trước khi hủy lệnh. Mặc định 30s.
    """
    try:
        res = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": res.returncode == 0,
            "exit_code": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Lệnh đã bị timeout sau {timeout} giây.",
        }
    except Exception as e:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Lỗi thực thi: {str(e)}",
        }


@mcp.tool()
def list_top_processes(sort_by: str = "cpu", limit: int = 10) -> str:
    """Liệt kê các tiến trình (processes) đang chạy, sắp xếp theo mức tiêu thụ tài nguyên.

    Args:
        sort_by: Sắp xếp theo 'cpu' hoặc 'mem' (mặc định: 'cpu').
        limit: Số lượng tiến trình cần lấy (mặc định: 10).
    """
    sort_flag = "-%cpu" if sort_by.lower() == "cpu" else "-%mem"
    cmd = f"ps -eo pid,user,%cpu,%mem,comm --sort={sort_flag} | head -n {limit + 1}"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else res.stderr


@mcp.tool()
def check_service_status(service_name: str) -> Dict[str, Any]:
    """Kiểm tra trạng thái của một systemd service trên Linux.

    Args:
        service_name: Tên service (ví dụ: 'sshd', 'nginx', 'firewalld', 'docker').
    """
    cmd = ["systemctl", "is-active", service_name]
    res_active = subprocess.run(cmd, capture_output=True, text=True)

    status_cmd = ["systemctl", "status", service_name, "-n", "5"]
    res_status = subprocess.run(status_cmd, capture_output=True, text=True)

    return {
        "service": service_name,
        "is_active": res_active.stdout.strip() == "active",
        "state": res_active.stdout.strip(),
        "details": res_status.stdout or res_status.stderr,
    }


@mcp.tool()
def read_system_logs(service_name: str = "", lines: int = 20) -> str:
    """Đọc nhật ký hệ thống gần nhất qua journalctl.

    Args:
        service_name: Tên unit/service cần lọc (tùy chọn). Để trống nếu muốn xem log chung.
        lines: Số dòng log gần nhất cần lấy (mặc định: 20).
    """
    cmd = f"journalctl -n {lines} --no-pager"
    if service_name:
        cmd += f" -u {service_name}"

    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else res.stderr


if __name__ == "__main__":
    # Chạy MCP Server giao tiếp qua Stdio
    mcp.run()
