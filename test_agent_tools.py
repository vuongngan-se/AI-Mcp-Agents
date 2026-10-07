import asyncio
import subprocess
from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams


# Định nghĩa các công cụ Python cho Agent
def read_file(path: str) -> str:
    """Đọc nội dung của một file từ đĩa."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Lỗi đọc file: {str(e)}"


def write_file(path: str, content: str) -> str:
    """Tạo mới hoặc ghi đè nội dung vào một file."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Đã ghi thành công vào file '{path}'"
    except Exception as e:
        return f"Lỗi ghi file: {str(e)}"


def run_command(command: str) -> str:
    """Thực thi một lệnh bash trong hệ thống và trả về kết quả."""
    try:
        res = subprocess.run(command, shell=True, capture_output=True, text=True)
        return res.stdout if res.returncode == 0 else (res.stderr or res.stdout)
    except Exception as e:
        return f"Lỗi thực thi lệnh: {str(e)}"


app = MCPApp(name="file_and_command_agent")


async def main():
    async with app.run():
        agent = Agent(
            name="system_assistant",
            instruction="""Bạn là một trợ lý hệ thống. Bạn có khả năng đọc file (read_file), 
            sửa/tạo file (write_file), và thực thi lệnh hệ thống (run_command). 
            Hãy thực hiện chính xác yêu cầu của người dùng bằng cách gọi các hàm phù hợp.""",
            functions=[read_file, write_file, run_command],
        )

        async with agent:
            llm = await agent.attach_llm(OpenAIAugmentedLLM)

            # Thử nghiệm bảo Agent thực thi 1 lệnh hệ thống và ghi kết quả vào file demo.txt
            prompt = (
                "Hãy dùng công cụ run_command để xem thư mục hiện tại (lệnh `ls -la`), "
                "sau đó ghi danh sách đó vào file 'demo.txt' bằng công cụ write_file."
            )

            print(f"👉 Yêu cầu: {prompt}\n")
            response = await llm.generate_str(
                prompt,
                request_params=RequestParams(model="gemini-3.6-flash"),
            )

            print("\n🤖 Phản hồi của Agent:")
            print(response)


if __name__ == "__main__":
    asyncio.run(main())
