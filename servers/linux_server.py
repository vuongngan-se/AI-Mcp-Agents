"""
Linux MCP Server (FastMCP)
Đồ án môn học: Linux và Mã nguồn mở
Đề tài: Build and Configure an MCP Server for Agentic AI in Linux
Kiến trúc: Microservice Daemon (Hỗ trợ SSE và Stdio)
Tác giả: AI SRE Team
"""

import argparse
import json
import os
import re
import shutil
import subprocess
from typing import Any, Dict
from mcp.server.fastmcp import FastMCP

# Khởi tạo FastMCP Server với cấu hình mặc định host 127.0.0.1 và port 8000
mcp = FastMCP("linux-system-monitor", host="127.0.0.1", port=8000)

# Biểu thức chính quy kiểm tra định dạng tên service: chỉ chấp nhận chữ cái, số, gạch dưới, gạch ngang, dấu chấm.
# Ngăn chặn hoàn toàn Command Injection (; && || | ` $ > < \n ...)
SERVICE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")

# Whitelist các dịch vụ an toàn được phép restart thông qua MCP Tool
ALLOWED_SERVICES = {"nginx", "postgresql", "redis-server"}


def validate_service_name(service_name: str) -> None:
    """Kiểm tra tính hợp lệ của tên service để phòng chống Command Injection."""
    if not service_name or not isinstance(service_name, str):
        raise ValueError("Tên service không được để trống và phải là chuỗi ký tự.")
    if not SERVICE_NAME_PATTERN.match(service_name):
        raise ValueError(
            f"Tên service '{service_name}' không hợp lệ. Chỉ cho phép các ký tự: a-z, A-Z, 0-9, '_', '-', '.'"
        )


@mcp.tool()
def check_service_status(service_name: str) -> Dict[str, Any]:
    """Kiểm tra trạng thái của một systemd service trên hệ thống Linux.
    
    Chạy lệnh 'systemctl status' và 'systemctl is-active' với timeout an toàn,
    không gây treo tiến trình (non-interactive, pager bị tắt).

    Args:
        service_name: Tên dịch vụ cần kiểm tra (ví dụ: 'nginx', 'postgresql', 'redis-server').
    """
    try:
        validate_service_name(service_name)
    except ValueError as err:
        return {
            "success": False,
            "service": service_name,
            "error": str(err),
            "is_active": False,
            "active_state": "invalid_name",
        }

    # 1. Kiểm tra trạng thái kích hoạt ngắn gọn (is-active)
    try:
        active_proc = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        active_state = active_proc.stdout.strip()
    except subprocess.TimeoutExpired:
        active_state = "timeout"
    except Exception as e:
        active_state = f"error: {str(e)}"

    # 2. Lấy thông tin chi tiết qua 'systemctl status'
    # Các tham số quan trọng:
    #   --no-pager: Ngăn chặn systemctl mở less/more gây treo I/O
    #   -n 15: Giới hạn 15 dòng nhật ký gần nhất đi kèm
    try:
        status_proc = subprocess.run(
            ["systemctl", "status", service_name, "--no-pager", "-n", "15"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        details = status_proc.stdout if status_proc.stdout else status_proc.stderr
        returncode = status_proc.returncode
    except subprocess.TimeoutExpired:
        details = "Lệnh 'systemctl status' đã bị hủy do timeout quá 8 giây."
        returncode = -1
    except Exception as e:
        details = f"Lỗi thực thi lệnh: {str(e)}"
        returncode = -1

    return {
        "success": returncode in [0, 3],  # 0: active, 3: inactive/failed
        "service": service_name,
        "is_active": active_state == "active",
        "active_state": active_state,
        "exit_code": returncode,
        "details": details.strip(),
    }


@mcp.tool()
def read_journal_logs(service_name: str, lines: int = 50) -> Dict[str, Any]:
    """Đọc nhật ký hoạt động của service từ systemd journal (journalctl).

    Args:
        service_name: Tên service cần trích xuất log (ví dụ: 'nginx').
        lines: Số dòng log mới nhất cần đọc (giới hạn an toàn từ 1 đến 500 dòng).
    """
    try:
        validate_service_name(service_name)
    except ValueError as err:
        return {"success": False, "service": service_name, "error": str(err), "logs": ""}

    # Giới hạn số dòng an toàn để tránh tràn bộ nhớ hoặc nghẽn mạng
    safe_lines = max(1, min(int(lines), 500))

    # Xây dựng danh sách tham số (tuyệt đối không dùng shell=True)
    cmd = ["journalctl", "-u", service_name, "-n", str(safe_lines), "--no-pager"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        logs = proc.stdout if proc.returncode == 0 else proc.stderr

        # Nếu unprivileged user không có quyền đọc trực tiếp journal, thử dùng sudo
        if "No journal files were opened" in logs or proc.returncode != 0:
            sudo_cmd = ["sudo", "journalctl", "-u", service_name, "-n", str(safe_lines), "--no-pager"]
            sudo_proc = subprocess.run(sudo_cmd, capture_output=True, text=True, timeout=10)
            if sudo_proc.returncode == 0:
                logs = sudo_proc.stdout

        return {
            "success": True,
            "service": service_name,
            "lines_requested": safe_lines,
            "logs": logs.strip() if logs else "(Không có log nào được ghi nhận)",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "service": service_name,
            "error": "Quá thời gian chờ (timeout 10s) khi đọc journalctl.",
            "logs": "",
        }
    except Exception as e:
        return {
            "success": False,
            "service": service_name,
            "error": f"Lỗi khi đọc log: {str(e)}",
            "logs": "",
        }


@mcp.tool()
def inspect_system_resources() -> Dict[str, Any]:
    """Đọc và thu thập thông số tài nguyên hệ thống Linux.
    
    Truy xuất trực tiếp các pseudo-filesystem (/proc/loadavg, /proc/meminfo)
    và ổ đĩa để đảm bảo tốc độ cao, tiêu tốn ít CPU và không phụ thuộc lệnh ngoài.
    """
    # 1. Đọc tải hệ thống (Load Average) từ /proc/loadavg
    load_info = {}
    try:
        with open("/proc/loadavg", "r", encoding="utf-8") as f:
            parts = f.read().strip().split()
            if len(parts) >= 5:
                load_info = {
                    "load_1min": float(parts[0]),
                    "load_5min": float(parts[1]),
                    "load_15min": float(parts[2]),
                    "runnable_tasks": parts[3],
                }
    except Exception as e:
        load_info = {"error": str(e)}

    # 2. Đọc thông số bộ nhớ RAM từ /proc/meminfo
    mem_info = {}
    try:
        mem_data = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    key, val = line.split(":", 1)
                    val_parts = val.strip().split()
                    if val_parts:
                        mem_data[key.strip()] = int(val_parts[0])  # đơn vị kB

        total_kb = mem_data.get("MemTotal", 0)
        free_kb = mem_data.get("MemFree", 0)
        avail_kb = mem_data.get("MemAvailable", free_kb)
        used_kb = total_kb - avail_kb

        mem_info = {
            "total_mb": round(total_kb / 1024, 2),
            "used_mb": round(used_kb / 1024, 2),
            "available_mb": round(avail_kb / 1024, 2),
            "usage_percent": round((used_kb / total_kb * 100), 2) if total_kb > 0 else 0,
            "swap_total_mb": round(mem_data.get("SwapTotal", 0) / 1024, 2),
            "swap_free_mb": round(mem_data.get("SwapFree", 0) / 1024, 2),
        }
    except Exception as e:
        mem_info = {"error": str(e)}

    # 3. Đọc thông số ổ đĩa gốc (Root Partition)
    disk_info = {}
    try:
        usage = shutil.disk_usage("/")
        disk_info = {
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "usage_percent": round((usage.used / usage.total) * 100, 2),
        }
    except Exception as e:
        disk_info = {"error": str(e)}

    # 4. Thời gian hoạt động (Uptime)
    uptime_info = "N/A"
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            total_seconds = float(f.read().split()[0])
            days = int(total_seconds // 86400)
            hours = int((total_seconds % 86400) // 3600)
            minutes = int((total_seconds % 3600) // 60)
            uptime_info = f"{days} days, {hours} hours, {minutes} minutes"
    except Exception:
        try:
            up_proc = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=3)
            uptime_info = up_proc.stdout.strip()
        except Exception:
            pass

    return {
        "load_average": load_info,
        "memory": mem_info,
        "disk": disk_info,
        "uptime": uptime_info,
        "cpu_cores": os.cpu_count(),
    }


@mcp.tool()
def restart_service(service_name: str) -> Dict[str, Any]:
    """Khởi động lại một dịch vụ hệ thống thông qua systemctl.
    
    CƠ CHẾ BẢO MẬT BẮT BUỘC:
    1. Kiểm tra Whitelist: Chỉ cho phép các dịch vụ nằm trong danh sách:
       ['nginx', 'postgresql', 'redis-server'].
    2. Ngăn chặn triệt để Command Injection bằng subprocess argument list.
    3. Thực thi qua sudo với cấu hình phân quyền tối thiểu (Least Privilege).

    Args:
        service_name: Tên dịch vụ cần restart.
    """
    try:
        validate_service_name(service_name)
    except ValueError as err:
        return {
            "success": False,
            "service": service_name,
            "error": str(err),
            "exit_code": -1,
        }

    # Kiểm tra Whitelist nghiêm ngặt
    if service_name not in ALLOWED_SERVICES:
        return {
            "success": False,
            "service": service_name,
            "error": (
                f"Từ chối quyền thực thi (Security Rejection): Dịch vụ '{service_name}' "
                f"không nằm trong danh sách Whitelist được cấp phép: {sorted(list(ALLOWED_SERVICES))}."
            ),
            "exit_code": -2,
        }

    # Thực thi lệnh sudo systemctl restart <service>
    cmd = ["sudo", "systemctl", "restart", service_name]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if proc.returncode == 0:
            return {
                "success": True,
                "service": service_name,
                "message": f"Dịch vụ '{service_name}' đã được khởi động lại thành công.",
                "exit_code": 0,
            }
        else:
            return {
                "success": False,
                "service": service_name,
                "error": proc.stderr.strip() or proc.stdout.strip() or "Khởi động lại thất bại.",
                "exit_code": proc.returncode,
            }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "service": service_name,
            "error": f"Lệnh khởi động lại dịch vụ '{service_name}' bị quá thời gian (timeout 15s).",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "service": service_name,
            "error": f"Lỗi hệ thống trong quá trình thực thi: {str(e)}",
            "exit_code": -1,
        }


if __name__ == "__main__":
    # Phân tích tham số dòng lệnh CLI
    parser = argparse.ArgumentParser(
        description="Linux MCP Server (FastMCP) - Hỗ trợ cả Microservice Daemon (SSE) và Stdio"
    )
    parser.add_argument(
        "--transport",
        choices=["sse", "stdio"],
        default="sse",
        help="Giao thức truyền thông: 'sse' (HTTP Server-Sent Events daemon) hoặc 'stdio'. Mặc định: 'sse'",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Địa chỉ IP lắng nghe (mặc định: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Cổng kết nối SSE (mặc định: 8000)",
    )
    args = parser.parse_args()

    if args.transport == "sse":
        print(f"🚀 Khởi chạy Linux MCP Server (SSE Daemon) tại http://{args.host}:{args.port}/sse ...")
        if hasattr(mcp, "settings"):
            mcp.settings.host = args.host
            mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        # Chạy chuẩn stdio transport tường minh (tránh cảnh báo thiếu transport)
        mcp.run(transport="stdio")
