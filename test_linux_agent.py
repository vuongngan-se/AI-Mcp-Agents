import asyncio
from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent

app = MCPApp(name="linux_sysadmin_test")


async def main():
    async with app.run() as agent_app:
        print("🚀 Khởi chạy MCPApp và kết nối tới MCP Server 'linux_system'...")
        
        # Khởi tạo Agent với server_names trỏ tới 'linux_system'
        agent = Agent(
            name="linux_admin",
            instruction="Bạn là chuyên viên quản trị hệ thống Linux cấp cao.",
            server_names=["linux_system"],
        )

        async with agent:
            print("🔍 Đang truy vấn danh sách tools từ linux_system server...")
            tools_list = await agent.list_tools()
            print(f"✅ Đã tìm thấy {len(tools_list.tools)} tools từ server:")
            for tool in tools_list.tools:
                print(f"  - 🛠️ {tool.name}: {tool.description.splitlines()[0] if tool.description else ''}")

            # Thử nghiệm gọi trực tiếp tool từ Agent qua MCP Server
            print("\n🧪 Thử gọi trực tiếp tool 'get_system_info' qua MCP Server...")
            sys_info = await agent.call_tool("get_system_info")
            print("📊 Kết quả trả về từ MCP Server:")
            print(sys_info)


if __name__ == "__main__":
    asyncio.run(main())
