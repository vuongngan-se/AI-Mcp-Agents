"""
Agent Orchestrator sử dụng Framework mcp-agent
Đồ án môn học: Linux và Mã nguồn mở
Đề tài: Build and Configure an MCP Server for Agentic AI in Linux
Vai trò Agent: Linux System Diagnostician
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict

from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent

# Khởi tạo MCP Application
app = MCPApp(name="linux_system_diagnostician_app")


async def execute_automated_incident_workflow(agent: Agent, incident_message: str):
    """
    Quy trình tự động hóa xử lý sự cố (Automated Incident Response Workflow)
    Thực hiện đầy đủ các bước:
      1. Nhận diện sự cố ('Website nginx báo lỗi 502 Bad Gateway')
      2. Kiểm tra tài nguyên tổng thể hệ thống (inspect_system_resources)
      3. Kiểm tra trạng thái chi tiết của Nginx service (check_service_status)
      4. Thu thập và phân tích nhật ký journalctl gần nhất (read_journal_logs)
      5. Đưa ra phán đoán kỹ thuật & thực thi restart an toàn (restart_service)
      6. Kiểm tra lại trạng thái sau khi can thiệp và xuất báo cáo sự cố (Post-mortem Report)
    """
    print("\n" + "=" * 70)
    print("🚨 [HỆ THỐNG GIÁM SÁT] PHÁT HIỆN SỰ CỐ DỊCH VỤ")
    print(f"   Thông báo: \"{incident_message}\"")
    print("=" * 70)

    # ---------------------------------------------------------
    # BƯỚC 1: Thu thập tài nguyên hệ thống Linux
    # ---------------------------------------------------------
    print("\n🔍 [Bước 1/5] Kiểm tra tài nguyên hệ thống (Load Average, Memory, Disk)...")
    res_call = await agent.call_tool("inspect_system_resources", {})
    resources = json.loads(res_call.content[0].text)

    load = resources.get("load_average", {})
    mem = resources.get("memory", {})
    disk = resources.get("disk", {})
    
    print(f"   • Uptime         : {resources.get('uptime')}")
    print(f"   • Load Average   : 1m={load.get('load_1min')}, 5m={load.get('load_5min')}, 15m={load.get('load_15min')}")
    print(f"   • RAM khả dụng   : {mem.get('available_mb')} MB / {mem.get('total_mb')} MB ({mem.get('usage_percent')}% đã dùng)")
    print(f"   • Dung lượng Root: {disk.get('free_gb')} GB trống / {disk.get('total_gb')} GB")

    if mem.get("usage_percent", 0) > 90:
        print("   ⚠️ CẢNH BÁO: Bộ nhớ RAM đang ở mức rất cao (>90%), có nguy cơ bị Linux OOM Killer tiêu diệt tiến trình!")

    # ---------------------------------------------------------
    # BƯỚC 2: Kiểm tra trạng thái Nginx Service
    # ---------------------------------------------------------
    print("\n🔍 [Bước 2/5] Kiểm tra trạng thái dịch vụ systemd 'nginx'...")
    status_call = await agent.call_tool("check_service_status", {"service_name": "nginx"})
    nginx_status = json.loads(status_call.content[0].text)

    is_active = nginx_status.get("is_active", False)
    active_state = nginx_status.get("active_state", "unknown")
    state_symbol = "🟢 ACTIVE" if is_active else "🔴 INACTIVE/FAILED"
    print(f"   • Trạng thái hiện tại: {state_symbol} ({active_state})")
    print(f"   • Exit code: {nginx_status.get('exit_code')}")

    # ---------------------------------------------------------
    # BƯỚC 3: Đọc và phân tích Journalctl Logs
    # ---------------------------------------------------------
    print("\n📜 [Bước 3/5] Đọc 25 dòng nhật ký gần nhất của service 'nginx' qua journalctl...")
    logs_call = await agent.call_tool("read_journal_logs", {"service_name": "nginx", "lines": 25})
    logs_data = json.loads(logs_call.content[0].text)
    logs_content = logs_data.get("logs", "")

    print("--- [ĐOẠN TRÍCH NHẬT KÝ JOURNALCTL] ---")
    log_preview = "\n".join(logs_content.splitlines()[-10:]) if logs_content else "(Không có log)"
    print(log_preview)
    print("---------------------------------------")

    # Phân tích nguyên nhân lỗi 502 Bad Gateway
    print("\n🧠 [Bước 4/5] Chuyên gia Linux Diagnostician phân tích nguyên nhân:")
    needs_restart = False
    if not is_active:
        print("   -> NGUYÊN NHÂN: Dịch vụ nginx đang ở trạng thái ngừng hoạt động hoặc đã bị crash,")
        print("      khiến Reverse Proxy/Gateway không thể xử lý request, gây ra lỗi 502 Bad Gateway.")
        needs_restart = True
    else:
        print("   -> Dịch vụ nginx đang active nhưng người dùng gặp lỗi 502 Bad Gateway.")
        print("      Nguyên nhân có thể do kết nối socket bị đơ, worker process gặp sự cố hoặc upstream backend tạm thời không phản hồi.")
        print("      Hành động đề xuất: Thực hiện restart graceful dịch vụ nginx để giải phóng worker processes và tái lập kết nối.")
        needs_restart = True

    # ---------------------------------------------------------
    # BƯỚC 4: Khởi động lại dịch vụ qua restart_service (Whitelist Protection)
    # ---------------------------------------------------------
    if needs_restart:
        print("\n⚙️  Thực hiện khôi phục: Gọi MCP tool 'restart_service' cho 'nginx'...")
        restart_call = await agent.call_tool("restart_service", {"service_name": "nginx"})
        restart_result = json.loads(restart_call.content[0].text)

        if restart_result.get("success"):
            print(f"   ✅ {restart_result.get('message')}")
        else:
            print(f"   ❌ Khởi động lại thất bại: {restart_result.get('error')}")

    # ---------------------------------------------------------
    # BƯỚC 5: Kiểm tra lại trạng thái sau khi can thiệp
    # ---------------------------------------------------------
    print("\n🔍 [Bước 5/5] Tái kiểm tra trạng thái sau khi khắc phục...")
    await asyncio.sleep(1)  # Đợi service khởi động hoàn tất
    post_check_call = await agent.call_tool("check_service_status", {"service_name": "nginx"})
    post_status = json.loads(post_check_call.content[0].text)

    post_active = post_status.get("is_active", False)
    final_symbol = "🟢 ACTIVE (Ổn định)" if post_active else "🔴 VẪN LỖI"
    print(f"   • Trạng thái Nginx sau restart: {final_symbol} ({post_status.get('active_state')})")

    # ---------------------------------------------------------
    # BÁO CÁO TỔNG KẾT SỰ CỐ (INCIDENT RESOLUTION REPORT)
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print("📋 BÁO CÁO KẾT THÚC XỬ LÝ SỰ CỐ (INCIDENT POST-MORTEM REPORT)")
    print("=" * 70)
    print(f"1. Vấn đề ghi nhận   : {incident_message}")
    print(f"2. Đối tượng kiểm tra: Dịch vụ web server/reverse proxy 'nginx'")
    print(f"3. Tình trạng ban đầu: is_active={is_active} (Trạng thái: {active_state})")
    print(f"4. Biện pháp áp dụng : Khởi động lại an toàn dịch vụ thông qua sudo systemctl")
    print(f"5. Kết quả can thiệp : {final_symbol}")
    print(f"6. Kết luận          : {'Sự cố 502 Bad Gateway đã được giải quyết thành công.' if post_active else 'Cần sự can thiệp thủ công sâu hơn từ Sysadmin.'}")
    print("=" * 70 + "\n")


async def main():
    """Hàm khởi chạy chính của chương trình."""
    print("🚀 Khởi tạo ứng dụng MCP App...")
    
    async with app.run() as agent_app:
        # Cấu hình Agent với vai trò "Linux System Diagnostician"
        diagnostician = Agent(
            name="linux_system_diagnostician",
            instruction="""Bạn là một kỹ sư Linux SRE & System Diagnostician cấp cao.
Nhiệm vụ của bạn là chẩn đoán lỗi hệ thống, kiểm tra nhật ký, phân tích các sự cố mạng và web server (như 502 Bad Gateway),
kiểm tra năng lực tài nguyên CPU/RAM/Disk, và thực hiện khắc phục dịch vụ theo đúng nguyên tắc bảo mật tối thiểu (Least Privilege).""",
            server_names=["linux_system"],
        )

        async with diagnostician:
            incident_prompt = "Website nginx báo lỗi 502 Bad Gateway"

            # Kiểm tra xem có cấu hình API Key của LLM (OpenAI, Gemini, Anthropic) hay không
            has_llm_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

            if has_llm_key:
                try:
                    from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
                    from mcp_agent.workflows.llm.augmented_llm import RequestParams

                    print("🤖 Đã phát hiện cấu hình LLM API Key. Kích hoạt Autonomous LLM Agent...")
                    llm = await diagnostician.attach_llm(OpenAIAugmentedLLM)
                    
                    full_prompt = (
                        f"SỰ CỐ HỆ THỐNG: '{incident_prompt}'.\n"
                        "Hãy thực hiện tuần tự:\n"
                        "1. Kiểm tra tài nguyên hệ thống bằng inspect_system_resources.\n"
                        "2. Kiểm tra trạng thái nginx bằng check_service_status.\n"
                        "3. Đọc 20 dòng nhật ký gần nhất bằng read_journal_logs để xác định nguyên nhân.\n"
                        "4. Thực hiện restart_service cho nginx nếu cần thiết.\n"
                        "5. Kiểm tra lại trạng thái sau khi restart và tóm tắt báo cáo xử lý sự cố."
                    )
                    
                    response = await llm.generate_str(
                        message=full_prompt,
                        request_params=RequestParams(model=os.getenv("LLM_MODEL", "gpt-4o-mini")),
                    )
                    print("\n" + "=" * 70)
                    print("🤖 PHẢN HỒI VÀ QUYẾT ĐỊNH TỪ AI AGENT (LLM):")
                    print("=" * 70)
                    print(response)
                    print("=" * 70)
                    return
                except Exception as ex:
                    print(f"⚠️ Không thể thực thi qua LLM ({ex}). Chuyển sang quy trình tự động hóa cứu hộ mặc định...")

            # Nếu không có LLM key hoặc gọi LLM bị lỗi, thực thi quy trình điều phối sự cố tự động
            print("ℹ️ Chạy chế độ Autonomous Deterministic Incident Workflow qua MCP Tools:")
            await execute_automated_incident_workflow(diagnostician, incident_prompt)


if __name__ == "__main__":
    asyncio.run(main())
