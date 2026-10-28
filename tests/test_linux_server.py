import pytest
from servers.linux_server import (
    get_system_info,
    execute_command,
    list_top_processes,
    check_service_status,
    read_system_logs,
)


def test_get_system_info():
    info = get_system_info()
    assert isinstance(info, dict)
    assert "os_name" in info
    assert "hostname" in info
    assert "cpu_count" in info
    assert "memory" in info
    assert "disk_root" in info
    assert info["cpu_count"] > 0
    assert info["disk_root"]["total_gb"] > 0


def test_execute_command_success():
    res = execute_command("echo 'MCP_TEST_SUCCESS'")
    assert isinstance(res, dict)
    assert res["success"] is True
    assert res["exit_code"] == 0
    assert "MCP_TEST_SUCCESS" in res["stdout"]


def test_execute_command_failure():
    res = execute_command("non_existent_command_12345")
    assert isinstance(res, dict)
    assert res["success"] is False
    assert res["exit_code"] != 0


def test_list_top_processes():
    output = list_top_processes(sort_by="cpu", limit=5)
    assert isinstance(output, str)
    assert len(output.strip()) > 0
    assert "PID" in output or "COMMAND" in output


def test_check_service_status():
    res = check_service_status("systemd-resolved")
    assert isinstance(res, dict)
    assert "service" in res
    assert "is_active" in res
    assert "state" in res


def test_read_system_logs():
    logs = read_system_logs(lines=5)
    assert isinstance(logs, str)
