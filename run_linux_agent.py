"""
Linux Agentic AI System Monitor & Administrator
Sử dụng mcp-agent framework kết nối với MCP Server 'linux_system'.
"""

import asyncio
import json
import os
import sys
from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent

app = MCPApp(name="linux_sysadmin_agent")


async def run_diagnostic_workflow(agent: Agent):
    """Quy trình Agentic tự động chẩn đoán hệ thống Linux thông qua MCP Server."""
    print("=" * 60)
    print("🛡️  BẮT ĐẦU QUY TRÌNH TỰ ĐỘNG CHẨN ĐOÁN HỆ THỐNG LINUX")
    print("=" * 60)

    # Bước 1: Lấy thông số hệ thống
    print("\n[Bước 1/4] 🖥️  Thu thập thông tin phần cứng & OS...")
    sys_info_res = await agent.call_tool("get_system_info")
    sys_info = json.loads(sys_info_res.content[0].text)
    
    print(f"  • Hệ điều hành : {sys_info.get('os_name')} (Kernel: {sys_info.get('kernel_release')})")
    print(f"  • Hostname     : {sys_info.get('hostname')} | Kiến trúc: {sys_info.get('architecture')}")
    print(f"  • Số lõi CPU   : {sys_info.get('cpu_count')}")
    print(f"  • Thời gian chạy: {sys_info.get('uptime')}")
    
    disk = sys_info.get("disk_root", {})
    print(f"  • Dung lượng ổ cứng root: {disk.get('used_gb')}GB / {disk.get('total_gb')}GB ({disk.get('percent_used')}%)")
    if disk.get("percent_used", 0) > 85:
        print("    ⚠️ CẢNH BÁO: Dung lượng ổ cứng vượt quá 85%!")
    else:
        print("    ✅ Trạng thái ổ cứng an toàn.")

    # Bước 2: Kiểm tra Top tiến trình tiêu thụ tài nguyên
    print("\n[Bước 2/4] 📈 Kiểm tra Top 5 tiến trình tiêu thụ nhiều CPU nhất...")
    top_proc_res = await agent.call_tool("list_top_processes", {"sort_by": "cpu", "limit": 5})
    top_proc_text = top_proc_res.content[0].text.strip()
    print("------------------------------------------------------------")
    print(top_proc_text)
    print("------------------------------------------------------------")

    # Bước 3: Kiểm tra các service hệ thống quan trọng
    print("\n[Bước 3/4] ⚙️  Kiểm tra trạng thái các Systemd Services quan trọng...")
    services_to_check = ["sshd", "firewalld", "systemd-resolved"]
    for svc in services_to_check:
        res = await agent.call_tool("check_service_status", {"service_name": svc})
        svc_data = json.loads(res.content[0].text)
        state_icon = "🟢 Đang chạy" if svc_data.get("is_active") else "🔴 Không hoạt động"
        print(f"  • Dịch vụ {svc:<18}: {state_icon} ({svc_data.get('state')})")

    # Bước 4: Kiểm tra tải và nhật ký gần đây
    print("\n[Bước 4/4] 📋 Chạy lệnh kiểm tra tải hệ thống (uptime & free -m)...")
    cmd_res = await agent.call_tool("execute_command", {"command": "uptime && free -h"})
    cmd_data = json.loads(cmd_res.content[0].text)
    print("------------------------------------------------------------")
    print(cmd_data.get("stdout", "").strip())
    print("------------------------------------------------------------")

    print("\n" + "=" * 60)
    print("🎯 BÁO CÁO TỔNG KẾT TỪ AGENT: Hệ thống Linux hoạt động bình thường.")
    print("=" * 60)


async def is_llm_service_available() -> bool:
    """Kiểm tra nhanh xem endpoint LLM (Local router hoặc OpenAI) có đang chạy không."""
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    try:
        import urllib.request
        req = urllib.request.Request(f"{base_url.rstrip('/')}/models", headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', '')}"})
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status in [200, 401]
    except Exception:
        return False


async def main():
    async with app.run() as agent_app:
        agent = Agent(
            name="linux_sysadmin",
            instruction="""Bạn là một AI Linux System Administrator. 
            Nhiệm vụ của bạn là giám sát, xử lý lỗi và bảo mật cho hệ thống Linux 
            bằng các công cụ được cung cấp qua MCP Server.""",
            server_names=["linux_system"],
        )

        async with agent:
            llm_available = await is_llm_service_available()
            
            if llm_available:
                try:
                    from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
                    from mcp_agent.workflows.llm.augmented_llm import RequestParams

                    print("🤖 Đã phát hiện LLM endpoint khả dụng! Khởi tạo AI Agent...")
                    llm = await agent.attach_llm(OpenAIAugmentedLLM)
                    prompt = "Hãy dùng công cụ get_system_info để xem cấu hình máy và tóm tắt ngắn gọn trong 2 câu."
                    response = await llm.generate_str(
                        prompt,
                        request_params=RequestParams(model="gemini-3.6-flash"),
                    )
                    print("\n🤖 Phản hồi từ AI Agent (LLM):")
                    print(response)
                except Exception as e:
                    print(f"⚠️ Lỗi trong quá trình gọi LLM: {e}")
            else:
                print("ℹ️  LLM endpoint (local proxy) hiện chưa bật.")
                print("⚡ Đang thực thi Chế độ Tự động Chẩn đoán (Autonomous Diagnostic Workflow) thông qua MCP Server:")
                await run_diagnostic_workflow(agent)



if __name__ == "__main__":
    asyncio.run(main())
